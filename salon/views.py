# UBICACIÓN: salon/views.py
import logging
import json
import requests
from datetime import timedelta, time, datetime
from dateutil.relativedelta import relativedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.utils.text import slugify 

from .models import Peluqueria, Servicio, Empleado, Cita, PerfilUsuario, HorarioEmpleado, Cupon, ConfiguracionPlataforma
from .forms import ServicioForm, RegistroPublicoEmpleadoForm
from .services import obtener_bloques_disponibles
from salon.utils.booking_lock import BookingManager

logger = logging.getLogger(__name__)

# =======================================================
# 1. AUTENTICACIÓN
# =======================================================

def login_custom(request):
    if request.user.is_authenticated: return redirigir_segun_rol(request.user)
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('email'), password=request.POST.get('password'))
        if user: login(request, user); return redirigir_segun_rol(user)
        else: return render(request, 'salon/login.html', {'error': 'Credenciales incorrectas'})
    return render(request, 'salon/login.html')

def redirigir_segun_rol(user):
    if user.is_superuser: return redirect('/admin/')
    try:
        if hasattr(user, 'perfil') and user.perfil.es_dueño: return redirect('panel_negocio')
    except: pass
    try:
        if hasattr(user, 'empleado_perfil'): return redirect('mi_agenda')
    except: pass
    return redirect('inicio')

def logout_view(request): logout(request); return redirect('inicio')

# =======================================================
# 2. REGISTRO SAAS Y PAGOS (LÓGICA BLINDADA)
# =======================================================

def landing_saas(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Crear Usuario
                user = User.objects.create_user(
                    username=request.POST.get('username_owner'), 
                    email=request.POST.get('email'), 
                    password=request.POST.get('password'), 
                    first_name=request.POST.get('nombre_owner'), 
                    last_name=request.POST.get('apellido_owner')
                )
                
                # Crear Peluquería
                slug = slugify(request.POST.get('nombre_negocio'))
                if Peluqueria.objects.filter(slug=slug).exists(): 
                    slug += f"-{int(datetime.now().timestamp())}"
                
                peluqueria = Peluqueria.objects.create(
                    nombre=request.POST.get('nombre_negocio'), 
                    slug=slug, 
                    telefono=request.POST.get('telefono', ''),
                    fecha_inicio_contrato=timezone.now()
                )
                
                # Asignar Perfil
                user.perfil.peluqueria = peluqueria
                user.perfil.es_dueño = True
                user.perfil.save()
                
                # Crear Empleado (Dueño también es empleado)
                Empleado.objects.create(
                    user=user, peluqueria=peluqueria, 
                    nombre=user.first_name, apellido=user.last_name, 
                    email_contacto=user.email, activo=True
                )
            
            # Notificación Telegram al Admin de la Plataforma
            config = ConfiguracionPlataforma.objects.first()
            if config and config.telegram_token:
                msg = f"💰 *NUEVO CLIENTE*\nNegocio: {peluqueria.nombre}\nUsuario: {user.email}\nEstado: Pendiente Pago"
                try:
                    requests.post(f"https://api.telegram.org/bot{config.telegram_token}/sendMessage", 
                                  data={"chat_id": config.telegram_chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=5)
                except: pass
            
            login(request, user)
            return redirect('pago_suscripcion_saas')

        except Exception as e:
            messages.error(request, f"Error en registro: {e}")
    return render(request, 'salon/landing_saas.html')

@login_required
def pago_suscripcion_saas(request):
    """
    Genera Link de Pago con API Bold (Server-to-Server).
    Solo requiere Secret Key.
    """
    if not request.user.perfil.es_dueño: return redirect('inicio')
    
    config = ConfiguracionPlataforma.objects.first()
    peluqueria = request.user.perfil.peluqueria
    
    # Credenciales de la Plataforma (TÚ cobras)
    secret_key = config.bold_secret_key if config else "te4T6sOL43wDlcGwCGHfGA"
    monto = config.precio_mensualidad if config else 130000
    
    if request.method == 'POST':
        # Referencia única para evitar duplicados
        ref = f"SUB-{peluqueria.id}-{int(datetime.now().timestamp())}"
        
        # Fecha de vencimiento (24 horas)
        expiracion = (datetime.now() + timedelta(days=1)).isoformat()

        url_bold = "https://integrations.api.bold.co/online/link/v1"
        headers = {
            "Authorization": f"x-api-key {secret_key}",
            "Content-Type": "application/json"
        }
        
        # Construir la URL de retorno
        scheme = "https" if request.is_secure() else "http"
        redirect_url = f"{scheme}://{request.get_host()}/negocio/dashboard/"

        payload = {
            "name": "Suscripción PASO Manager",
            "description": f"Mensualidad salón {peluqueria.nombre}",
            "amount": monto,
            "currency": "COP",
            "sku": ref,
            "expiration_date": expiracion,
            "redirection_url": redirect_url
        }
        
        try:
            r = requests.post(url_bold, json=payload, headers=headers)
            if r.status_code == 201: 
                return redirect(r.json()["payload"]["url"]) # Redirige a Bold
            else: 
                err_msg = r.json().get('message') or r.text
                messages.error(request, f"Error Bold ({r.status_code}): {err_msg}")
        except Exception as e: 
            messages.error(request, "Error de conexión.")
            logger.error(e)

    return render(request, 'salon/pago_suscripcion.html', {'monto': monto, 'peluqueria': peluqueria})

# =======================================================
# 3. PANEL DE CONTROL (DUEÑO)
# =======================================================

@login_required
def panel_negocio(request):
    if not request.user.perfil.es_dueño: return redirect('inicio')
    peluqueria = request.user.perfil.peluqueria
    hoy = timezone.localdate()
    
    # --- Lógica Fechas de Corte ---
    inicio = peluqueria.fecha_inicio_contrato.date()
    proximo = inicio
    while proximo <= hoy: proximo += relativedelta(months=1)
    
    dias = (proximo - hoy).days
    anterior = proximo - relativedelta(months=1)
    dias_mora = (hoy - anterior).days

    alerta, estado = None, "activo"
    
    if dias <= 3 and dias >= 0: 
        estado = "advertencia"
        alerta = f"⚠️ Tu corte es el {proximo.day}. Tienes {dias} días para pagar."
    elif dias < 0: 
        if dias_mora <= 3: 
            estado = "gracia"
            alerta = f"🚨 Fecha superada. Estás en tus 3 días de cortesía."
        else: 
            estado = "vencido"
            alerta = "⛔ Cuenta vencida. Paga para reactivar."

    # --- Guardar Configuración ---
    if request.method == 'POST':
        accion = request.POST.get('accion')
        
        if accion == 'guardar_config':
            peluqueria.direccion = request.POST.get('direccion')
            peluqueria.telefono = request.POST.get('telefono')
            peluqueria.hora_apertura = request.POST.get('hora_apertura')
            peluqueria.hora_cierre = request.POST.get('hora_cierre')
            peluqueria.porcentaje_abono = int(request.POST.get('porcentaje_abono'))
            
            # Credenciales del DUEÑO (para cobrar a sus clientes)
            peluqueria.bold_api_key = request.POST.get('bold_api_key')
            peluqueria.bold_secret_key = request.POST.get('bold_secret_key')
            peluqueria.bold_integrity_key = request.POST.get('bold_integrity_key')
            
            peluqueria.telegram_token = request.POST.get('telegram_token')
            peluqueria.telegram_chat_id = request.POST.get('telegram_chat_id')
            
            peluqueria.save()
            messages.success(request, "Configuración guardada correctamente.")
            
        elif accion == 'crear_cupon':
            Cupon.objects.create(
                peluqueria=peluqueria, 
                codigo=request.POST.get('codigo_cupon').upper(), 
                porcentaje_descuento=int(request.POST.get('porcentaje')), 
                usos_restantes=int(request.POST.get('cantidad', 100))
            )
            messages.success(request, "Cupón creado.")
            
        elif accion == 'eliminar_cupon':
            Cupon.objects.filter(id=request.POST.get('cupon_id'), peluqueria=peluqueria).delete()
            messages.success(request, "Cupón eliminado.")
            
        return redirect('panel_negocio')

    ctx = {
        'peluqueria': peluqueria, 
        'alerta_pago': alerta, 
        'estado_cuenta': estado, 
        'proximo_pago': proximo,
        'citas_hoy': peluqueria.citas.filter(fecha_hora_inicio__date=hoy).count(),
        'ingresos_mes': peluqueria.citas.filter(fecha_hora_inicio__month=hoy.month, estado='C').aggregate(Sum('precio_total'))['precio_total__sum'] or 0,
        'empleados': peluqueria.empleados.all(),
        'servicios': peluqueria.servicios.all(),
        'cupones': peluqueria.cupones.all(),
        'link_invitacion': request.build_absolute_uri(f"/{peluqueria.slug}/unirse-al-equipo/")
    }
    return render(request, 'salon/dashboard.html', ctx)

# =======================================================
# 4. GESTIÓN DE NEGOCIO (SERVICIOS Y EQUIPO - RESTAURADOS)
# =======================================================

@login_required
def gestionar_servicios(request):
    if not hasattr(request.user, 'perfil') or not request.user.perfil.es_dueño: return redirect('inicio')
    peluqueria = request.user.perfil.peluqueria
    
    if request.method == 'POST':
        form = ServicioForm(request.POST)
        if form.is_valid():
            nuevo = form.save(commit=False)
            nuevo.peluqueria = peluqueria
            nuevo.duracion = timedelta(minutes=form.cleaned_data['duracion_minutos'])
            nuevo.save()
            messages.success(request, "Servicio creado.")
            return redirect('gestionar_servicios')
    else:
        form = ServicioForm()
    
    return render(request, 'salon/panel_dueño/servicios.html', {
        'servicios': peluqueria.servicios.all(), 
        'form': form, 
        'peluqueria': peluqueria
    })

@login_required
def eliminar_servicio(request, servicio_id):
    if not hasattr(request.user, 'perfil') or not request.user.perfil.es_dueño: return redirect('inicio')
    s = get_object_or_404(Servicio, id=servicio_id, peluqueria=request.user.perfil.peluqueria)
    s.delete()
    messages.success(request, "Servicio eliminado.")
    return redirect('gestionar_servicios')

@login_required
def gestionar_equipo(request):
    if not hasattr(request.user, 'perfil') or not request.user.perfil.es_dueño: return redirect('inicio')
    peluqueria = request.user.perfil.peluqueria
    link_invitacion = request.build_absolute_uri(f"/{peluqueria.slug}/unirse-al-equipo/")
    return render(request, 'salon/panel_dueño/equipo.html', {
        'peluqueria': peluqueria, 
        'empleados': peluqueria.empleados.all(), 
        'link_invitacion': link_invitacion
    })

# =======================================================
# 5. EMPLEADOS Y AGENDA (RESTAURADOS)
# =======================================================

@login_required
def mi_agenda(request):
    try: empleado = request.user.empleado_perfil
    except: return redirect('login_custom')
    
    if request.method == 'POST':
        with transaction.atomic():
            HorarioEmpleado.objects.filter(empleado=empleado).delete()
            for i in range(7):
                if request.POST.get(f'trabaja_{i}'):
                    HorarioEmpleado.objects.create(
                        empleado=empleado, dia_semana=i,
                        hora_inicio=request.POST.get(f'inicio_{i}'),
                        hora_fin=request.POST.get(f'fin_{i}'),
                        almuerzo_inicio=request.POST.get(f'almuerzo_inicio_{i}') or None,
                        almuerzo_fin=request.POST.get(f'almuerzo_fin_{i}') or None
                    )
        messages.success(request, "Horario actualizado.")
        return redirect('mi_agenda')
        
    horarios = {h.dia_semana: h for h in HorarioEmpleado.objects.filter(empleado=empleado)}
    lista_dias = []
    dias_nombres = {0:'Lunes',1:'Martes',2:'Miércoles',3:'Jueves',4:'Viernes',5:'Sábado',6:'Domingo'}
    for i, nombre in dias_nombres.items():
        h = horarios.get(i)
        lista_dias.append({
            'id': i, 'nombre': nombre, 'trabaja': h is not None,
            'inicio': h.hora_inicio.strftime('%H:%M') if h else '09:00',
            'fin': h.hora_fin.strftime('%H:%M') if h else '19:00',
            'l_ini': h.almuerzo_inicio.strftime('%H:%M') if (h and h.almuerzo_inicio) else '',
            'l_fin': h.almuerzo_fin.strftime('%H:%M') if (h and h.almuerzo_fin) else ''
        })
    
    mis_citas = Cita.objects.filter(empleado=empleado, fecha_hora_inicio__gte=datetime.now()).order_by('fecha_hora_inicio')
    return render(request, 'salon/mi_horario.html', {'empleado': empleado, 'dias': lista_dias, 'mis_citas': mis_citas})

def registro_empleado_publico(request, slug_peluqueria):
    peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)
    if request.method == 'POST':
        form = RegistroPublicoEmpleadoForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            if User.objects.filter(username=data['email']).exists():
                return render(request, 'salon/registro_empleado.html', {'peluqueria': peluqueria, 'form': form, 'error': 'Correo ya registrado'})
            
            with transaction.atomic():
                u = User.objects.create_user(username=data['email'], email=data['email'], password=data['password'], first_name=data['nombre'], last_name=data['apellido'])
                u.perfil.peluqueria = peluqueria; u.perfil.es_dueño = False; u.perfil.save()
                emp = Empleado.objects.create(peluqueria=peluqueria, user=u, nombre=data['nombre'], apellido=data['apellido'], email_contacto=data['email'], activo=True)
                for i in range(7): HorarioEmpleado.objects.create(empleado=emp, dia_semana=i, hora_inicio=time(9,0), hora_fin=time(19,0))
            
            login(request, u); return redirect('mi_agenda')
    else: form = RegistroPublicoEmpleadoForm()
    return render(request, 'salon/registro_empleado.html', {'peluqueria': peluqueria, 'form': form})

# =======================================================
# 6. PÁGINA PÚBLICA Y RESERVAS (RESTAURADAS)
# =======================================================

def inicio(request):
    peluquerias = Peluqueria.objects.all()
    ciudades = Peluqueria.objects.values_list('ciudad', flat=True).distinct()
    return render(request, 'salon/index.html', {'peluquerias': peluquerias, 'ciudades': ciudades})

def agendar_cita(request, slug_peluqueria):
    peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)
    servicios = peluqueria.servicios.all()
    empleados = peluqueria.empleados.filter(activo=True)
    
    if request.method == 'POST':
        try:
            # Recopilación de datos
            emp_id = request.POST.get('empleado')
            fecha = request.POST.get('fecha_seleccionada')
            hora = request.POST.get('hora_seleccionada')
            servicios_ids = request.POST.getlist('servicios')
            
            if not (emp_id and fecha and hora and servicios_ids):
                raise ValueError("Faltan datos obligatorios.")
            
            servs = Servicio.objects.filter(id__in=servicios_ids)
            duracion = sum([s.duracion for s in servs], timedelta())
            precio = sum([s.precio for s in servs])
            
            inicio_dt = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
            fin_dt = inicio_dt + duracion
            
            # Función de reserva segura
            def _reserva(empleado):
                if Cita.objects.filter(empleado=empleado, estado__in=['P','C'], fecha_hora_inicio__lt=fin_dt, fecha_hora_fin__gt=inicio_dt).exists():
                    raise ValueError("Horario ocupado.")
                cita = Cita.objects.create(
                    peluqueria=peluqueria, empleado=empleado,
                    cliente_nombre=request.POST.get('nombre_cliente'),
                    cliente_telefono=request.POST.get('telefono_cliente'),
                    fecha_hora_inicio=inicio_dt, fecha_hora_fin=fin_dt,
                    precio_total=precio, estado='P'
                )
                cita.servicios.set(servs)
                return cita
                
            cita = BookingManager.ejecutar_reserva_segura(emp_id, _reserva)
            cita.enviar_notificacion_telegram()
            
            # Redirigir a confirmación / pago del cliente
            return redirect('confirmacion_cita', slug_peluqueria=peluqueria.slug, cita_id=cita.id)
            
        except Exception as e:
            return render(request, 'salon/agendar.html', {'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados, 'error_mensaje': str(e)})
            
    return render(request, 'salon/agendar.html', {'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados})

def api_obtener_horarios(request):
    emp_id = request.GET.get('empleado_id')
    fecha_str = request.GET.get('fecha')
    if not emp_id or not fecha_str: return JsonResponse({'horas': []})
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        emp = Empleado.objects.get(id=emp_id)
        # Lógica simplificada de duración por defecto o real
        horas = obtener_bloques_disponibles(emp, fecha, timedelta(minutes=30))
        return JsonResponse({'horas': horas})
    except: return JsonResponse({'horas': []})

def confirmacion_cita(request, slug_peluqueria, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    # Lógica para mostrar botón de pago al cliente final
    # Usamos las llaves del CLIENTE (Peluquería), no las tuyas
    peluqueria = cita.peluqueria
    
    # Calcular firma integridad si fuera necesario (aquí simplificado)
    # Si quieres usar el botón simple para clientes también:
    return render(request, 'salon/pago_bold.html', {
        'cita': cita, 
        'peluqueria': peluqueria,
        'monto_anticipo': int(cita.precio_total * (peluqueria.porcentaje_abono/100)),
        'referencia': f"CITA-{cita.id}",
        'signature': "INTEGRITY_HASH_PENDIENTE" # Aquí iría la lógica de integridad si usas botón
    })

def retorno_bold(request):
    return render(request, 'salon/confirmacion.html')
