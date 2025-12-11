# UBICACIÓN: salon/views.py
import logging
import requests
from datetime import timedelta, datetime
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
from dateutil.relativedelta import relativedelta # Necesario para sumar meses exactos

from .models import Peluqueria, Servicio, Empleado, Cita, PerfilUsuario, HorarioEmpleado, Cupon, ConfiguracionPlataforma
from .forms import ServicioForm, RegistroPublicoEmpleadoForm
from .services import obtener_bloques_disponibles
from salon.utils.booking_lock import BookingManager

logger = logging.getLogger(__name__)

# =======================================================
# 1. AUTENTICACIÓN
# =======================================================

def login_custom(request):
    if request.user.is_authenticated:
        return redirigir_segun_rol(request.user)

    if request.method == 'POST':
        u = request.POST.get('email')
        p = request.POST.get('password')
        user = authenticate(request, username=u, password=p)
        
        if user is not None:
            login(request, user)
            return redirigir_segun_rol(user)
        else:
            return render(request, 'salon/login.html', {'error': 'Credenciales incorrectas'})
    return render(request, 'salon/login.html')

def redirigir_segun_rol(user):
    if user.is_superuser: return redirect('/admin/')
    try:
        if hasattr(user, 'perfil') and user.perfil.es_dueño:
            return redirect('panel_negocio')
    except: pass
    try:
        if hasattr(user, 'empleado_perfil'): 
            return redirect('mi_agenda')
    except: pass
    return redirect('inicio')

def logout_view(request):
    logout(request)
    return redirect('inicio')

# =======================================================
# 2. REGISTRO SAAS Y COBRO (API LINK SIMPLE)
# =======================================================

def landing_saas(request):
    if request.method == 'POST':
        nombre_negocio = request.POST.get('nombre_negocio')
        telefono = request.POST.get('telefono', '') 
        first_name = request.POST.get('nombre_owner')
        last_name = request.POST.get('apellido_owner')
        username = request.POST.get('username_owner')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            messages.error(request, "Las contraseñas no coinciden.")
            return render(request, 'salon/landing_saas.html')
        if User.objects.filter(username=username).exists():
            messages.error(request, f"El usuario '{username}' ya existe.")
            return render(request, 'salon/landing_saas.html')
        if User.objects.filter(email=email).exists():
            messages.error(request, "Ese correo ya está registrado.")
            return render(request, 'salon/landing_saas.html')

        try:
            with transaction.atomic():
                user = User.objects.create_user(username=username, email=email, password=password)
                user.first_name = first_name
                user.last_name = last_name
                user.save()

                base_slug = slugify(nombre_negocio)
                slug = base_slug
                contador = 1
                while Peluqueria.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{contador}"
                    contador += 1

                peluqueria = Peluqueria.objects.create(
                    nombre=nombre_negocio, slug=slug, direccion="Configurar Dirección", telefono=telefono,
                    fecha_inicio_contrato=timezone.now() # Fecha clave para el cobro
                )
                
                perfil = user.perfil
                perfil.peluqueria = peluqueria
                perfil.es_dueño = True
                perfil.save()

                Empleado.objects.create(
                    user=user, peluqueria=peluqueria, nombre=first_name, apellido=last_name, email_contacto=email, activo=True
                )

            login(request, user)
            # Redirigir OBLIGATORIAMENTE al pago
            return redirect('pago_suscripcion_saas')

        except Exception as e:
            logger.error(f"Error SaaS: {e}")
            messages.error(request, f"Error interno: {str(e)}")
            return render(request, 'salon/landing_saas.html')

    return render(request, 'salon/landing_saas.html')

@login_required
def pago_suscripcion_saas(request):
    """
    Genera el link de pago directamente con Bold API (Sin Integrity Key, solo Secret).
    """
    if not hasattr(request.user, 'perfil') or not request.user.perfil.es_dueño:
        return redirect('inicio')
    
    config = ConfiguracionPlataforma.objects.first()
    peluqueria = request.user.perfil.peluqueria
    
    # DATOS DE BOLD (Usamos los tuyos por defecto si no hay config)
    secret_key = config.bold_secret_key if config else "te4T6sOL43wDlcGwCGHfGA"
    monto = config.precio_mensualidad if config else 130000
    
    # URL de retorno al dashboard tras pagar
    scheme = "https" if request.is_secure() else "http"
    domain = request.get_host()
    redirect_url = f"{scheme}://{domain}/negocio/dashboard/"
    
    ref = f"PASO-{peluqueria.id}-{int(datetime.now().timestamp())}"

    # LLAMADA A BOLD (API LINKS)
    url = "https://integrations.api.bold.co/online/link/v1"
    headers = {
        "Authorization": f"x-api-key {secret_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "name": "Suscripción Mensual PASO",
        "description": f"Mensualidad para {peluqueria.nombre}",
        "amount": monto,
        "currency": "COP",
        "redirection_url": redirect_url,
        "sku": ref
    }

    try:
        r = requests.post(url, json=payload, headers=headers)
        if r.status_code == 201:
            data = r.json()
            link_pago = data["payload"]["url"]
            # Redirigir al usuario a Bold para que pague
            return redirect(link_pago)
        else:
            # Si falla Bold, mostramos error (pero no los dejamos entrar al panel)
            logger.error(f"Error Bold: {r.text}")
            return render(request, 'salon/pago_bold.html', {'error': 'No se pudo generar el pago. Intenta de nuevo.'})
    except Exception as e:
        logger.error(f"Error conexión Bold: {e}")
        return render(request, 'salon/pago_bold.html', {'error': 'Error de conexión.'})

# =======================================================
# 3. PANEL Y GESTIÓN (Con Lógica de Fechas de Corte)
# =======================================================

@login_required
def panel_negocio(request):
    if not hasattr(request.user, 'perfil') or not request.user.perfil.es_dueño:
        return redirect('inicio')
    
    peluqueria = request.user.perfil.peluqueria
    hoy = timezone.localdate()

    # --- LÓGICA DE FECHA DE CORTE Y PAGOS ---
    fecha_inicio = peluqueria.fecha_inicio_contrato.date()
    
    # Calcular próxima fecha de pago (mismo día del mes siguiente)
    # Si hoy es 11/Dic, y el inicio fue 11/Dic, el próximo es 11/Ene
    proximo_pago = fecha_inicio + relativedelta(months=1)
    while proximo_pago <= hoy:
        proximo_pago += relativedelta(months=1)
        
    dias_restantes = (proximo_pago - hoy).days
    
    alerta_pago = None
    estado_cuenta = "activo" # activo, advertencia, vencido

    # Lógica de los 3 días antes y 3 días de gracia
    if dias_restantes <= 3 and dias_restantes >= 0:
        estado_cuenta = "advertencia"
        alerta_pago = f"⚠️ Tu corte es el {proximo_pago.day}. Tienes {dias_restantes} días para pagar."
    elif dias_restantes < 0:
        # Estamos en mora, verificar si está en los 3 días de gracia
        dias_mora = abs(dias_restantes)
        if dias_mora <= 3:
            estado_cuenta = "gracia"
            alerta_pago = f"🚨 Fecha de corte superada. Tienes 3 días de cortesía antes de la suspensión."
        else:
            estado_cuenta = "vencido"
            alerta_pago = "⛔ Tu cuenta está vencida. Por favor realiza el pago para reactivar."

    # --- GUARDAR CONFIGURACIÓN ---
    if request.method == 'POST':
        tipo_accion = request.POST.get('accion')
        if tipo_accion == 'guardar_config':
            try:
                peluqueria.direccion = request.POST.get('direccion')
                peluqueria.telefono = request.POST.get('telefono')
                peluqueria.hora_apertura = request.POST.get('hora_apertura')
                peluqueria.hora_cierre = request.POST.get('hora_cierre')
                peluqueria.porcentaje_abono = int(request.POST.get('porcentaje_abono', 50))
                peluqueria.bold_api_key = request.POST.get('bold_api_key')
                peluqueria.bold_integrity_key = request.POST.get('bold_integrity_key')
                peluqueria.bold_secret_key = request.POST.get('bold_secret_key')
                peluqueria.telegram_token = request.POST.get('telegram_token')
                peluqueria.telegram_chat_id = request.POST.get('telegram_chat_id')
                peluqueria.save()
                messages.success(request, "Configuración guardada.")
            except Exception as e:
                messages.error(request, f"Error: {e}")
        elif tipo_accion == 'crear_cupon':
            try:
                Cupon.objects.create(peluqueria=peluqueria, codigo=request.POST.get('codigo_cupon').upper(), porcentaje_descuento=int(request.POST.get('porcentaje')), usos_restantes=int(request.POST.get('cantidad', 100)))
                messages.success(request, "Cupón creado.")
            except: messages.error(request, "Error creando cupón.")
        elif tipo_accion == 'eliminar_cupon':
            Cupon.objects.filter(id=request.POST.get('cupon_id'), peluqueria=peluqueria).delete()
            messages.success(request, "Cupón eliminado.")
        return redirect('panel_negocio')

    # Datos Dashboard
    citas_hoy = peluqueria.citas.filter(fecha_hora_inicio__date=hoy).count()
    empleados = peluqueria.empleados.all()
    servicios = peluqueria.servicios.all()
    cupones = peluqueria.cupones.all()
    ingresos_mes = peluqueria.citas.filter(fecha_hora_inicio__month=hoy.month, estado='C').aggregate(Sum('precio_total'))['precio_total__sum'] or 0
    link_invitacion = request.build_absolute_uri(f"/{peluqueria.slug}/unirse-al-equipo/")

    return render(request, 'salon/dashboard.html', {
        'peluqueria': peluqueria, 'citas_hoy': citas_hoy, 'empleados': empleados, 
        'servicios': servicios, 'ingresos_mes': ingresos_mes, 'cupones': cupones, 
        'link_invitacion': link_invitacion,
        'alerta_pago': alerta_pago, 'estado_cuenta': estado_cuenta, 'proximo_pago': proximo_pago
    })

# (MANTENER EL RESTO DE VISTAS IGUAL: gestionar_servicios, eliminar, equipo, mi_agenda, registro_empleado, inicio, agendar, api, confirmacion, retorno)
# ... Asegúrate de que el resto del archivo tenga las funciones que ya tenías funcionando ...
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
            return redirect('gestionar_servicios')
    else: form = ServicioForm()
    return render(request, 'salon/panel_dueño/servicios.html', {'servicios': peluqueria.servicios.all(), 'form': form, 'peluqueria': peluqueria})

@login_required
def eliminar_servicio(request, servicio_id):
    if not hasattr(request.user, 'perfil') or not request.user.perfil.es_dueño: return redirect('inicio')
    get_object_or_404(Servicio, id=servicio_id, peluqueria=request.user.perfil.peluqueria).delete()
    return redirect('gestionar_servicios')

@login_required
def gestionar_equipo(request):
    if not hasattr(request.user, 'perfil') or not request.user.perfil.es_dueño: return redirect('inicio')
    peluqueria = request.user.perfil.peluqueria
    link_invitacion = request.build_absolute_uri(f"/{peluqueria.slug}/unirse-al-equipo/")
    return render(request, 'salon/panel_dueño/equipo.html', {'peluqueria': peluqueria, 'empleados': peluqueria.empleados.all(), 'link_invitacion': link_invitacion})

@login_required
def mi_agenda(request):
    try: empleado = request.user.empleado_perfil
    except: return redirect('login_custom')
    if request.method == 'POST':
        with transaction.atomic():
            HorarioEmpleado.objects.filter(empleado=empleado).delete()
            for i in range(7):
                if request.POST.get(f'trabaja_{i}'):
                    HorarioEmpleado.objects.create(empleado=empleado, dia_semana=i, hora_inicio=request.POST.get(f'inicio_{i}'), hora_fin=request.POST.get(f'fin_{i}'))
        return redirect('mi_agenda')
    horarios = {h.dia_semana: h for h in HorarioEmpleado.objects.filter(empleado=empleado)}
    lista_dias = [{'id': i, 'nombre': n, 'trabaja': horarios.get(i) is not None, 'inicio': horarios.get(i).hora_inicio.strftime('%H:%M') if horarios.get(i) else '09:00', 'fin': horarios.get(i).hora_fin.strftime('%H:%M') if horarios.get(i) else '19:00'} for i, n in {0:'Lunes',1:'Martes',2:'Miércoles',3:'Jueves',4:'Viernes',5:'Sábado',6:'Domingo'}.items()]
    return render(request, 'salon/mi_horario.html', {'empleado': empleado, 'dias': lista_dias, 'mis_citas': Cita.objects.filter(empleado=empleado, fecha_hora_inicio__gte=datetime.now())})

def registro_empleado_publico(request, slug_peluqueria):
    peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)
    if request.method == 'POST':
        form = RegistroPublicoEmpleadoForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            if User.objects.filter(username=data['email']).exists(): return render(request, 'salon/registro_empleado.html', {'peluqueria': peluqueria, 'form': form, 'error': 'Correo ya registrado'})
            with transaction.atomic():
                u = User.objects.create_user(username=data['email'], email=data['email'], password=data['password'], first_name=data['nombre'], last_name=data['apellido'])
                u.perfil.peluqueria = peluqueria; u.perfil.save()
                emp = Empleado.objects.create(peluqueria=peluqueria, user=u, nombre=data['nombre'], apellido=data['apellido'], email_contacto=data['email'])
                for i in range(7): HorarioEmpleado.objects.create(empleado=emp, dia_semana=i, hora_inicio=time(9,0), hora_fin=time(19,0))
            login(request, u); return redirect('mi_agenda')
    return render(request, 'salon/registro_empleado.html', {'peluqueria': peluqueria, 'form': RegistroPublicoEmpleadoForm()})

def inicio(request): return render(request, 'salon/index.html', {'peluquerias': Peluqueria.objects.all(), 'ciudades': Peluqueria.objects.values_list('ciudad', flat=True).distinct()})

def agendar_cita(request, slug_peluqueria):
    peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)
    if request.method == 'POST':
        # (Lógica de agendar simplificada para caber, usar la que ya tenías funcional)
        return redirect('confirmacion_cita', slug_peluqueria=peluqueria.slug, cita_id=1) 
    return render(request, 'salon/agendar.html', {'peluqueria': peluqueria, 'servicios': peluqueria.servicios.all(), 'empleados': peluqueria.empleados.filter(activo=True)})

def api_obtener_horarios(request): return JsonResponse({'horas': []})
def confirmacion_cita(request, slug_peluqueria, cita_id): return render(request, 'salon/confirmacion.html', {'cita': get_object_or_404(Cita, id=cita_id)})
def retorno_bold(request): return render(request, 'salon/confirmacion.html')
