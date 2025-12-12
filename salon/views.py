# UBICACIÓN: salon/views.py
import logging
import json
import requests
import hashlib
from datetime import timedelta, time, datetime
from dateutil.relativedelta import relativedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Sum, Q
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.utils.text import slugify 
from django.urls import reverse

from .models import Peluqueria, Servicio, Empleado, Cita, HorarioEmpleado, Cupon, ConfiguracionPlataforma, Ausencia
from .forms import ServicioForm, RegistroPublicoEmpleadoForm, AusenciaForm
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
# 2. SAAS: REGISTRO Y PAGOS
# =======================================================

def landing_saas(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                if User.objects.filter(username=request.POST.get('email')).exists():
                    raise ValueError("El correo ya está registrado.")

                user = User.objects.create_user(
                    username=request.POST.get('username_owner', request.POST.get('email')), 
                    email=request.POST.get('email'), 
                    password=request.POST.get('password'), 
                    first_name=request.POST.get('nombre_owner'), 
                    last_name=request.POST.get('apellido_owner')
                )
                
                slug = slugify(request.POST.get('nombre_negocio'))
                if Peluqueria.objects.filter(slug=slug).exists(): 
                    slug += f"-{int(datetime.now().timestamp())}"
                
                peluqueria = Peluqueria.objects.create(
                    nombre=request.POST.get('nombre_negocio'), 
                    slug=slug, 
                    telefono=request.POST.get('telefono', ''),
                    fecha_inicio_contrato=timezone.now()
                )
                
                user.perfil.peluqueria = peluqueria
                user.perfil.es_dueño = True
                user.perfil.save()
                
                Empleado.objects.create(
                    user=user, peluqueria=peluqueria, 
                    nombre=user.first_name, apellido=user.last_name, 
                    email_contacto=user.email, activo=True
                )
            
            # Notificación
            config = ConfiguracionPlataforma.objects.first()
            if config and config.telegram_token:
                try:
                    msg = f"💰 *NUEVO SAAS*\nNegocio: {peluqueria.nombre}\nUser: {user.email}"
                    requests.post(f"https://api.telegram.org/bot{config.telegram_token}/sendMessage", 
                                  data={"chat_id": config.telegram_chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=3)
                except: pass
            
            login(request, user)
            return redirect('pago_suscripcion_saas')

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return render(request, 'salon/landing_saas.html')
    return render(request, 'salon/landing_saas.html')

@login_required
def pago_suscripcion_saas(request):
    if not request.user.perfil.es_dueño: return redirect('inicio')
    
    peluqueria = request.user.perfil.peluqueria
    config = ConfiguracionPlataforma.objects.first()
    
    monto = config.precio_mensualidad if config else 130000
    link_respaldo = config.link_pago_bold if config else "#"
    
    if request.method == 'POST':
        if not config or not config.bold_secret_key:
            return redirect(link_respaldo)

        try:
            ref = f"SUB-{peluqueria.id}-{int(datetime.now().timestamp())}"
            url_bold = "https://integrations.api.bold.co/online/link/v1"
            headers = {"Authorization": f"x-api-key {config.bold_secret_key}", "Content-Type": "application/json"}
            
            redirect_url = request.build_absolute_uri(reverse('panel_negocio'))

            payload = {
                "name": "Suscripción PASO",
                "description": f"Plan Mensual {peluqueria.nombre}",
                "amount": monto,
                "currency": "COP",
                "sku": ref,
                "expiration_date": (datetime.now() + timedelta(days=1)).isoformat(),
                "redirection_url": redirect_url
            }
            
            r = requests.post(url_bold, json=payload, headers=headers, timeout=10)
            if r.status_code == 201:
                return redirect(r.json()["payload"]["url"])
            else:
                logger.error(f"Error Bold: {r.text}")
                return redirect(link_respaldo)
        except Exception as e:
            logger.error(f"Excepción Bold: {e}")
            return redirect(link_respaldo)

    return render(request, 'salon/pago_suscripcion.html', {'monto': monto, 'peluqueria': peluqueria})

# =======================================================
# 3. PANEL DUEÑO
# =======================================================

@login_required
def panel_negocio(request):
    if not request.user.perfil.es_dueño: return redirect('inicio')
    peluqueria = request.user.perfil.peluqueria
    hoy = timezone.localdate()
    
    inicio = peluqueria.fecha_inicio_contrato.date()
    proximo = inicio
    while proximo <= hoy: proximo += relativedelta(months=1)
    dias_restantes = (proximo - hoy).days
    
    alerta = None
    if dias_restantes <= 5:
        alerta = f"⚠️ Tu plan vence en {dias_restantes} días. Recuerda pagar."

    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'guardar_config':
            peluqueria.direccion = request.POST.get('direccion')
            peluqueria.telefono = request.POST.get('telefono')
            peluqueria.hora_apertura = request.POST.get('hora_apertura')
            peluqueria.hora_cierre = request.POST.get('hora_cierre')
            peluqueria.porcentaje_abono = int(request.POST.get('porcentaje_abono') or 50)
            
            # Credenciales Bold
            peluqueria.bold_api_key = request.POST.get('bold_api_key')
            peluqueria.bold_integrity_key = request.POST.get('bold_integrity_key')
            peluqueria.bold_secret_key = request.POST.get('bold_secret_key')
            
            # Credenciales Nequi (Manual)
            peluqueria.nequi_celular = request.POST.get('nequi_celular')
            if 'nequi_qr_imagen' in request.FILES:
                peluqueria.nequi_qr_imagen = request.FILES['nequi_qr_imagen']
            
            peluqueria.telegram_token = request.POST.get('telegram_token')
            peluqueria.telegram_chat_id = request.POST.get('telegram_chat_id')
            peluqueria.save()
            messages.success(request, "Configuración guardada.")
            
        elif accion == 'crear_cupon':
            Cupon.objects.create(peluqueria=peluqueria, codigo=request.POST.get('codigo_cupon'), porcentaje_descuento=int(request.POST.get('porcentaje')))
        elif accion == 'eliminar_cupon':
            Cupon.objects.filter(id=request.POST.get('cupon_id')).delete()
            
        return redirect('panel_negocio')

    ctx = {
        'peluqueria': peluqueria, 
        'alerta_pago': alerta, 
        'proximo_pago': proximo,
        'citas_hoy': peluqueria.citas.filter(fecha_hora_inicio__date=hoy).count(),
        'empleados': peluqueria.empleados.all(),
        'servicios': peluqueria.servicios.all(),
        'cupones': peluqueria.cupones.all(),
        'link_invitacion': request.build_absolute_uri(reverse('registro_empleado', args=[peluqueria.slug]))
    }
    return render(request, 'salon/dashboard.html', ctx)

# =======================================================
# 4. GESTIÓN DE SERVICIOS Y EQUIPO
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
    else: form = ServicioForm()
    return render(request, 'salon/panel_dueño/servicios.html', {'servicios': peluqueria.servicios.all(), 'form': form, 'peluqueria': peluqueria})

@login_required
def eliminar_servicio(request, servicio_id):
    s = get_object_or_404(Servicio, id=servicio_id, peluqueria=request.user.perfil.peluqueria)
    s.delete()
    return redirect('gestionar_servicios')

@login_required
def gestionar_equipo(request):
    if not request.user.perfil.es_dueño: return redirect('inicio')
    peluqueria = request.user.perfil.peluqueria
    link = request.build_absolute_uri(reverse('registro_empleado', args=[peluqueria.slug]))
    return render(request, 'salon/panel_dueño/equipo.html', {'peluqueria': peluqueria, 'empleados': peluqueria.empleados.all(), 'link_invitacion': link})

# =======================================================
# 5. EMPLEADOS Y AUSENCIAS
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

@login_required
def gestionar_ausencias(request):
    try: empleado = request.user.empleado_perfil
    except: return redirect('inicio')

    if request.method == 'POST':
        form = AusenciaForm(request.POST)
        if form.is_valid():
            ausencia = form.save(commit=False)
            ausencia.empleado = empleado
            ausencia.save()
            messages.success(request, "Ausencia registrada.")
            return redirect('gestionar_ausencias')
    else:
        form = AusenciaForm()

    ausencias = Ausencia.objects.filter(empleado=empleado, fecha_fin__gte=timezone.now()).order_by('fecha_inicio')
    return render(request, 'salon/ausencias.html', {'form': form, 'ausencias': ausencias, 'empleado': empleado})

@login_required
def eliminar_ausencia(request, ausencia_id):
    ausencia = get_object_or_404(Ausencia, id=ausencia_id, empleado__user=request.user)
    ausencia.delete()
    return redirect('gestionar_ausencias')

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
# 6. PÁGINA PÚBLICA Y RESERVAS
# =======================================================

def inicio(request):
    peluquerias = Peluqueria.objects.all()
    ciudades = Peluqueria.objects.values_list('ciudad', flat=True).distinct()
    return render(request, 'salon/index.html', {'peluquerias': peluquerias, 'ciudades': ciudades})

def agendar_cita(request, slug_peluqueria):
    peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)
    servicios = peluqueria.servicios.all()
    empleados = peluqueria.empleados.filter(activo=True)
    
    tiene_bold = bool(peluqueria.bold_api_key and peluqueria.bold_integrity_key)
    tiene_nequi = bool(peluqueria.nequi_celular)
    
    if request.method == 'POST':
        try:
            emp_id = request.POST.get('empleado')
            fecha = request.POST.get('fecha_seleccionada')
            hora = request.POST.get('hora_seleccionada')
            servicios_ids = request.POST.getlist('servicios')
            metodo_pago = request.POST.get('metodo_pago', 'SITIO') 
            
            if not (emp_id and fecha and hora and servicios_ids): raise ValueError("Faltan datos obligatorios.")
            
            servs = Servicio.objects.filter(id__in=servicios_ids)
            duracion = sum([s.duracion for s in servs], timedelta())
            precio = sum([s.precio for s in servs])
            
            inicio_dt = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
            fin_dt = inicio_dt + duracion
            
            def _reserva(empleado):
                if Ausencia.objects.filter(empleado=empleado, fecha_inicio__lt=fin_dt, fecha_fin__gt=inicio_dt).exists():
                    raise ValueError("El estilista tiene una ausencia programada en este horario.")

                if Cita.objects.filter(empleado=empleado, estado__in=['P','C'], fecha_hora_inicio__lt=fin_dt, fecha_hora_fin__gt=inicio_dt).exists():
                    raise ValueError("Horario ya ocupado.")
                
                cita = Cita.objects.create(
                    peluqueria=peluqueria, empleado=empleado,
                    cliente_nombre=request.POST.get('nombre_cliente'),
                    cliente_telefono=request.POST.get('telefono_cliente'),
                    fecha_hora_inicio=inicio_dt, fecha_hora_fin=fin_dt,
                    precio_total=precio, estado='P', 
                    metodo_pago=metodo_pago
                )
                cita.servicios.set(servs)
                return cita
                
            cita = BookingManager.ejecutar_reserva_segura(emp_id, _reserva)
            cita.enviar_notificacion_telegram()
            
            if metodo_pago == 'BOLD' and tiene_bold:
                return redirect('confirmacion_cita', slug_peluqueria=peluqueria.slug, cita_id=cita.id)
            elif metodo_pago == 'NEQUI' and tiene_nequi:
                return render(request, 'salon/pago_nequi.html', {'cita': cita, 'peluqueria': peluqueria})
            else:
                cita.estado = 'C' 
                cita.save()
                return render(request, 'salon/confirmacion.html', {'cita': cita, 'mensaje': '¡Reserva Confirmada!'})
            
        except Exception as e:
            return render(request, 'salon/agendar.html', {
                'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados, 
                'error_mensaje': str(e), 'tiene_bold': tiene_bold, 'tiene_nequi': tiene_nequi
            })
            
    return render(request, 'salon/agendar.html', {
        'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados,
        'tiene_bold': tiene_bold, 'tiene_nequi': tiene_nequi
    })

def confirmacion_cita(request, slug_peluqueria, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    peluqueria = cita.peluqueria
    
    if not peluqueria.bold_api_key or not peluqueria.bold_integrity_key:
        return render(request, 'salon/confirmacion.html', {'cita': cita, 'mensaje': 'Cita agendada (Pago en sitio)'})

    ref = f"CITA-{cita.id}-{int(datetime.now().timestamp())}"
    monto_abono = int(cita.precio_total * (peluqueria.porcentaje_abono/100))
    raw_sig = f"{ref}{monto_abono}COP{peluqueria.bold_integrity_key}"
    signature = hashlib.sha256(raw_sig.encode()).hexdigest()
    
    return render(request, 'salon/pago_bold.html', {
        'cita': cita, 'peluqueria': peluqueria, 'monto_anticipo': monto_abono,
        'referencia': ref, 'signature': signature, 'bold_api_key': peluqueria.bold_api_key
    })

def api_obtener_horarios(request):
    emp_id = request.GET.get('empleado_id')
    fecha_str = request.GET.get('fecha')
    if not emp_id or not fecha_str: return JsonResponse({'horas': []})
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        emp = Empleado.objects.get(id=emp_id)
        horas = obtener_bloques_disponibles(emp, fecha, timedelta(minutes=30))
        return JsonResponse({'horas': horas})
    except: return JsonResponse({'horas': []})

def retorno_bold(request):
    return render(request, 'salon/confirmacion.html', {'mensaje': 'Pago procesado exitosamente.'})
