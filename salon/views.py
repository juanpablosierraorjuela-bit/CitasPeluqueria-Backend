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

# --- AUTENTICACIÓN ---
def login_custom(request):
    if request.user.is_authenticated: return redirigir_segun_rol(request.user)
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('email'), password=request.POST.get('password'))
        if user: login(request, user); return redirigir_segun_rol(user)
        else: return render(request, 'salon/login.html', {'error': 'Credenciales incorrectas'})
    return render(request, 'salon/login.html')

def redirigir_segun_rol(user):
    if user.is_superuser: return redirect('/admin/')
    if hasattr(user, 'perfil') and user.perfil.es_dueño: return redirect('panel_negocio')
    if hasattr(user, 'empleado_perfil'): return redirect('mi_agenda')
    return redirect('inicio')

def logout_view(request): logout(request); return redirect('inicio')

# --- SAAS Y COBROS ---
def landing_saas(request):
    """ Registro de clientes nuevos. Redirige OBLIGATORIAMENTE al pago. """
    if request.method == 'POST':
        try:
            with transaction.atomic():
                user = User.objects.create_user(username=request.POST.get('username_owner'), email=request.POST.get('email'), password=request.POST.get('password'), first_name=request.POST.get('nombre_owner'), last_name=request.POST.get('apellido_owner'))
                slug = slugify(request.POST.get('nombre_negocio'))
                if Peluqueria.objects.filter(slug=slug).exists(): slug += f"-{int(datetime.now().timestamp())}"
                
                peluqueria = Peluqueria.objects.create(
                    nombre=request.POST.get('nombre_negocio'), slug=slug, telefono=request.POST.get('telefono', ''),
                    fecha_inicio_contrato=timezone.now()
                )
                user.perfil.peluqueria = peluqueria; user.perfil.es_dueño = True; user.perfil.save()
                Empleado.objects.create(user=user, peluqueria=peluqueria, nombre=user.first_name, apellido=user.last_name, email_contacto=user.email, activo=True)
            
            # Notificación Telegram
            config = ConfiguracionPlataforma.objects.first()
            if config and config.telegram_token:
                msg = f"💰 *NUEVO CLIENTE*\nNegocio: {peluqueria.nombre}\nUsuario: {user.email}"
                requests.post(f"https://api.telegram.org/bot{config.telegram_token}/sendMessage", data={"chat_id": config.telegram_chat_id, "text": msg, "parse_mode": "Markdown"})
            
            login(request, user)
            return redirect('pago_suscripcion_saas')
        except Exception as e:
            messages.error(request, f"Error: {e}")
    return render(request, 'salon/landing_saas.html')

@login_required
def pago_suscripcion_saas(request):
    if not request.user.perfil.es_dueño: return redirect('inicio')
    
    config = ConfiguracionPlataforma.objects.first()
    peluqueria = request.user.perfil.peluqueria
    secret_key = config.bold_secret_key if config else "te4T6sOL43wDlcGwCGHfGA"
    monto = config.precio_mensualidad if config else 130000
    
    if request.method == 'POST':
        ref = f"SUB-{peluqueria.id}-{int(datetime.now().timestamp())}"
        headers = {"Authorization": f"x-api-key {secret_key}", "Content-Type": "application/json"}
        payload = {
            "name": "Suscripción Mensual PASO", "description": f"Pago mensual {peluqueria.nombre}",
            "amount": monto, "currency": "COP", "sku": ref,
            "redirection_url": f"{'https' if request.is_secure() else 'http'}://{request.get_host()}/negocio/dashboard/"
        }
        
        try:
            r = requests.post("https://integrations.api.bold.co/online/link/v1", json=payload, headers=headers)
            if r.status_code == 201: return redirect(r.json()["payload"]["url"])
            else: 
                # AQUÍ ESTABA EL ERROR: Ahora mostramos el mensaje en la misma página
                error_msg = r.json().get('message', 'Error desconocido de Bold')
                messages.error(request, f"Error Bold: {error_msg}")
        except Exception as e: messages.error(request, "Error de conexión con Bold.")

    return render(request, 'salon/pago_suscripcion.html', {'monto': monto, 'peluqueria': peluqueria})

# --- PANEL DUEÑO ---
@login_required
def panel_negocio(request):
    if not request.user.perfil.es_dueño: return redirect('inicio')
    peluqueria = request.user.perfil.peluqueria
    hoy = timezone.localdate()
    
    # Lógica Fechas
    inicio = peluqueria.fecha_inicio_contrato.date()
    proximo = inicio + relativedelta(months=1)
    while proximo <= hoy: proximo += relativedelta(months=1)
    dias = (proximo - hoy).days
    
    alerta = None
    estado = "activo"
    if dias <= 3 and dias >= 0: estado = "advertencia"; alerta = f"⚠️ Corte en {dias} días."
    elif dias < 0: 
        if abs(dias) <= 3: estado = "gracia"; alerta = "🚨 Días de gracia activos."
        else: estado = "vencido"; alerta = "⛔ Cuenta vencida."

    if request.method == 'POST':
        if request.POST.get('accion') == 'guardar_config':
            peluqueria.bold_api_key = request.POST.get('bold_api_key')
            peluqueria.telegram_token = request.POST.get('telegram_token')
            peluqueria.save(); messages.success(request, "Guardado.")
        return redirect('panel_negocio')

    ctx = {
        'peluqueria': peluqueria, 'alerta_pago': alerta, 'estado_cuenta': estado, 'proximo_pago': proximo,
        'citas_hoy': peluqueria.citas.filter(fecha_hora_inicio__date=hoy).count(),
        'link_invitacion': request.build_absolute_uri(f"/{peluqueria.slug}/unirse-al-equipo/")
    }
    return render(request, 'salon/dashboard.html', ctx)

# --- RESTO DE VISTAS ---
def inicio(request): return render(request, 'salon/index.html', {'peluquerias': Peluqueria.objects.all(), 'ciudades': Peluqueria.objects.values_list('ciudad', flat=True).distinct()})
def registro_empleado_publico(request, slug_peluqueria): return render(request, 'salon/registro_empleado.html', {'peluqueria': get_object_or_404(Peluqueria, slug=slug_peluqueria)})
def agendar_cita(request, slug_peluqueria): return render(request, 'salon/agendar.html', {'peluqueria': get_object_or_404(Peluqueria, slug=slug_peluqueria)})
def api_obtener_horarios(request): return JsonResponse({'horas': []})
def confirmacion_cita(request, slug_peluqueria, cita_id): return render(request, 'salon/confirmacion.html')
def retorno_bold(request): return render(request, 'salon/confirmacion.html')
def gestionar_servicios(request): return render(request, 'salon/panel_dueño/servicios.html')
def eliminar_servicio(request, id): return redirect('gestionar_servicios')
def gestionar_equipo(request): return render(request, 'salon/panel_dueño/equipo.html')
def mi_agenda(request): return render(request, 'salon/mi_horario.html')
