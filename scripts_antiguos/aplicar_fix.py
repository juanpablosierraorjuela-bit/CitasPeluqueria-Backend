import os

# --- CONTENIDO 1: salon/services.py ---
# Usamos comillas simples triples (''') para evitar conflicto con las dobles (""") del código
services_code = r'''import pytz
from datetime import timedelta, datetime
from django.utils import timezone
from .models import Cita, Ausencia, HorarioEmpleado

# Intervalo de los bloques de tiempo (cada cuánto inicia una cita)
INTERVALO_MINUTOS = 30

def obtener_bloques_disponibles(empleado, fecha_date, duracion_servicio):
    """
    Calcula los bloques de inicio disponibles para un servicio de X duración.
    """
    dia_semana = fecha_date.weekday() # 0=Lunes, 6=Domingo
    
    # Zona Horaria Colombia para evitar desfases
    zona_co = pytz.timezone('America/Bogota')

    try:
        horario = HorarioEmpleado.objects.get(empleado=empleado, dia_semana=dia_semana)
    except HorarioEmpleado.DoesNotExist:
        return []

    bloques = []
    
    # 1. Crear fechas con Zona Horaria Correcta (Colombia)
    inicio_turno = timezone.make_aware(datetime.combine(fecha_date, horario.hora_inicio), zona_co)
    fin_turno = timezone.make_aware(datetime.combine(fecha_date, horario.hora_fin), zona_co)
    
    inicio_almuerzo = None
    fin_almuerzo = None
    if horario.almuerzo_inicio and horario.almuerzo_fin:
        inicio_almuerzo = timezone.make_aware(datetime.combine(fecha_date, horario.almuerzo_inicio), zona_co)
        fin_almuerzo = timezone.make_aware(datetime.combine(fecha_date, horario.almuerzo_fin), zona_co)

    # 2. Obtener Citas y Ausencias que SOLAPEN con el turno
    citas = Cita.objects.filter(
        empleado=empleado, 
        estado__in=['C', 'P'], 
        fecha_hora_fin__gt=inicio_turno,
        fecha_hora_inicio__lt=fin_turno
    )
    
    ausencias = Ausencia.objects.filter(
        empleado=empleado, 
        fecha_fin__gt=inicio_turno,
        fecha_inicio__lt=fin_turno
    )

    hora_actual = inicio_turno

    # 3. Iterar bloques
    while hora_actual + duracion_servicio <= fin_turno:
        fin_bloque = hora_actual + duracion_servicio
        ocupado = False

        if inicio_almuerzo and fin_almuerzo:
            if (hora_actual < fin_almuerzo) and (fin_bloque > inicio_almuerzo):
                ocupado = True

        if not ocupado:
            for c in citas:
                if (hora_actual < c.fecha_hora_fin) and (fin_bloque > c.fecha_hora_inicio):
                    ocupado = True; break
        
        if not ocupado:
            for a in ausencias:
                if (hora_actual < a.fecha_fin) and (fin_bloque > a.fecha_inicio):
                    ocupado = True; break
            
        if not ocupado: 
            bloques.append(hora_actual.strftime("%H:%M"))
        
        hora_actual += timedelta(minutes=INTERVALO_MINUTOS)
            
    return bloques

def verificar_conflicto_atomic(empleado, inicio, fin):
    return Cita.objects.filter(
        empleado=empleado, 
        estado__in=['P', 'C'],
        fecha_hora_inicio__lt=fin, 
        fecha_hora_fin__gt=inicio
    ).exists()
'''

# --- CONTENIDO 2: salon/views.py ---
views_code = r'''import logging, json, requests
from datetime import timedelta, time, datetime
from dateutil.relativedelta import relativedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.contrib import messages
from django.utils import timezone
from django.utils.text import slugify 
from django.urls import reverse
from django.http import JsonResponse
from .models import Peluqueria, Servicio, Empleado, Cita, HorarioEmpleado, ConfiguracionPlataforma, Ausencia
from .forms import ServicioForm, RegistroPublicoEmpleadoForm, AusenciaForm
from .services import obtener_bloques_disponibles
from salon.utils.booking_lock import BookingManager

logger = logging.getLogger(__name__)

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

def landing_saas(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                if User.objects.filter(username=request.POST.get('email')).exists(): raise ValueError("El correo ya está registrado.")
                user = User.objects.create_user(username=request.POST.get('username_owner', request.POST.get('email')), email=request.POST.get('email'), password=request.POST.get('password'), first_name=request.POST.get('nombre_owner'), last_name=request.POST.get('apellido_owner'))
                slug = slugify(request.POST.get('nombre_negocio'))
                if Peluqueria.objects.filter(slug=slug).exists(): slug += f"-{int(datetime.now().timestamp())}"
                peluqueria = Peluqueria.objects.create(nombre=request.POST.get('nombre_negocio'), slug=slug, telefono=request.POST.get('telefono', ''), fecha_inicio_contrato=timezone.now())
                user.perfil.peluqueria = peluqueria; user.perfil.es_dueño = True; user.perfil.save()
                Empleado.objects.create(user=user, peluqueria=peluqueria, nombre=user.first_name, apellido=user.last_name, email_contacto=user.email, activo=True)
            config = ConfiguracionPlataforma.objects.first()
            if config and config.telegram_token:
                try: requests.post(f"https://api.telegram.org/bot{config.telegram_token}/sendMessage", data={"chat_id": config.telegram_chat_id, "text": f"💰 *NUEVO SAAS*\nNegocio: {peluqueria.nombre}", "parse_mode": "Markdown"}, timeout=3)
                except: pass
            login(request, user); return redirect('pago_suscripcion_saas')
        except Exception as e: messages.error(request, f"Error: {str(e)}")
    return render(request, 'salon/landing_saas.html')

@login_required
def pago_suscripcion_saas(request):
    if not request.user.perfil.es_dueño: return redirect('inicio')
    peluqueria = request.user.perfil.peluqueria
    config = ConfiguracionPlataforma.objects.first()
    monto = config.precio_mensualidad if config else 130000
    if request.method == 'POST':
        if config and config.bold_secret_key:
            try:
                ref = f"SUB-{peluqueria.id}-{int(datetime.now().timestamp())}"
                url = "https://integrations.api.bold.co/online/link/v1"
                headers = {"Authorization": f"x-api-key {config.bold_secret_key}", "Content-Type": "application/json"}
                payload = {"name": "Suscripción PASO", "description": f"Plan Mensual {peluqueria.nombre}", "amount": monto, "currency": "COP", "sku": ref, "expiration_date": (datetime.now() + timedelta(days=1)).isoformat(), "redirection_url": request.build_absolute_uri(reverse('panel_negocio'))}
                r = requests.post(url, json=payload, headers=headers, timeout=10)
                if r.status_code == 201: return redirect(r.json()["payload"]["url"])
            except: pass
        return redirect(config.link_pago_bold) if config else redirect('panel_negocio')
    return render(request, 'salon/pago_suscripcion.html', {'monto': monto, 'peluqueria': peluqueria})

@login_required
def panel_negocio(request):
    if not request.user.perfil.es_dueño: return redirect('inicio')
    peluqueria = request.user.perfil.peluqueria
    hoy = timezone.localdate()
    inicio = peluqueria.fecha_inicio_contrato.date()
    proximo = inicio
    while proximo <= hoy: proximo += relativedelta(months=1)
    dias = (proximo - hoy).days
    alerta = f"⚠️ Tu plan vence en {dias} días." if dias <= 5 else None

    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'test_telegram':
            token, chat = request.POST.get('telegram_token'), request.POST.get('telegram_chat_id')
            peluqueria.telegram_token = token; peluqueria.telegram_chat_id = chat; peluqueria.save()
            try:
                r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat, "text": "✅ *PASO Manager:* Conexión Exitosa.", "parse_mode": "Markdown"}, timeout=5)
                if r.status_code == 200: messages.success(request, "Mensaje de prueba enviado.")
                else: messages.error(request, "Telegram falló. Revisa token/chat_id.")
            except: messages.error(request, "Error de conexión con Telegram.")
        elif accion == 'guardar_info':
            peluqueria.direccion = request.POST.get('direccion'); peluqueria.telefono = request.POST.get('telefono'); peluqueria.hora_apertura = request.POST.get('hora_apertura'); peluqueria.hora_cierre = request.POST.get('hora_cierre'); peluqueria.save(); messages.success(request, "Información guardada.")
        elif accion == 'guardar_pagos':
            peluqueria.porcentaje_abono = int(request.POST.get('porcentaje_abono') or 50); peluqueria.bold_api_key = request.POST.get('bold_api_key'); peluqueria.bold_secret_key = request.POST.get('bold_secret_key'); peluqueria.nequi_celular = request.POST.get('nequi_celular')
            if 'nequi_qr_imagen' in request.FILES: peluqueria.nequi_qr_imagen = request.FILES['nequi_qr_imagen']
            if request.POST.get('borrar_qr') == 'si': peluqueria.nequi_qr_imagen = None
            peluqueria.save(); messages.success(request, "Pagos actualizados.")
        return redirect('panel_negocio')

    citas_hoy = peluqueria.citas.filter(fecha_hora_inicio__date=hoy).order_by('fecha_hora_inicio')
    citas_futuras = peluqueria.citas.filter(fecha_hora_inicio__gte=timezone.now()).order_by('fecha_hora_inicio')[:20]
    ctx = {'peluqueria': peluqueria, 'alerta_pago': alerta, 'proximo_pago': proximo, 'citas_hoy_count': citas_hoy.count(), 'citas_futuras': citas_futuras, 'empleados': peluqueria.empleados.all(), 'servicios': peluqueria.servicios.all(), 'link_invitacion': request.build_absolute_uri(reverse('registro_empleado', args=[peluqueria.slug]))}
    return render(request, 'salon/dashboard.html', ctx)

@login_required
def gestionar_servicios(request):
    peluqueria = request.user.perfil.peluqueria
    if request.method == 'POST':
        form = ServicioForm(request.POST)
        if form.is_valid():
            nuevo = form.save(commit=False); nuevo.peluqueria = peluqueria; nuevo.duracion = timedelta(minutes=form.cleaned_data['duracion_minutos']); nuevo.save(); messages.success(request, "Servicio creado."); return redirect('gestionar_servicios')
    return render(request, 'salon/panel_dueño/servicios.html', {'servicios': peluqueria.servicios.all(), 'form': ServicioForm(), 'peluqueria': peluqueria})

@login_required
def eliminar_servicio(request, servicio_id):
    get_object_or_404(Servicio, id=servicio_id, peluqueria=request.user.perfil.peluqueria).delete(); return redirect('gestionar_servicios')

@login_required
def gestionar_equipo(request):
    peluqueria = request.user.perfil.peluqueria
    link = request.build_absolute_uri(reverse('registro_empleado', args=[peluqueria.slug]))
    return render(request, 'salon/panel_dueño/equipo.html', {'peluqueria': peluqueria, 'empleados': peluqueria.empleados.all(), 'link_invitacion': link})

@login_required
def mi_agenda(request):
    try: empleado = request.user.empleado_perfil
    except: return redirect('login_custom')
    if request.method == 'POST':
        HorarioEmpleado.objects.filter(empleado=empleado).delete()
        for i in range(7):
            if request.POST.get(f'trabaja_{i}'): HorarioEmpleado.objects.create(empleado=empleado, dia_semana=i, hora_inicio=request.POST.get(f'inicio_{i}'), hora_fin=request.POST.get(f'fin_{i}'), almuerzo_inicio=request.POST.get(f'almuerzo_inicio_{i}') or None, almuerzo_fin=request.POST.get(f'almuerzo_fin_{i}') or None)
        messages.success(request, "Horario actualizado."); return redirect('mi_agenda')
    horarios = {h.dia_semana: h for h in HorarioEmpleado.objects.filter(empleado=empleado)}
    lista = [{'id': i, 'nombre': n, 'trabaja': horarios.get(i) is not None, 'inicio': horarios.get(i).hora_inicio.strftime('%H:%M') if horarios.get(i) else '09:00', 'fin': horarios.get(i).hora_fin.strftime('%H:%M') if horarios.get(i) else '19:00', 'l_ini': horarios.get(i).almuerzo_inicio.strftime('%H:%M') if (horarios.get(i) and horarios.get(i).almuerzo_inicio) else '', 'l_fin': horarios.get(i).almuerzo_fin.strftime('%H:%M') if (horarios.get(i) and horarios.get(i).almuerzo_fin) else ''} for i, n in {0:'Lunes',1:'Martes',2:'Miércoles',3:'Jueves',4:'Viernes',5:'Sábado',6:'Domingo'}.items()]
    citas = Cita.objects.filter(empleado=empleado, fecha_hora_inicio__gte=datetime.now()).order_by('fecha_hora_inicio')
    return render(request, 'salon/mi_horario.html', {'empleado': empleado, 'dias': lista, 'mis_citas': citas})

@login_required
def gestionar_ausencias(request):
    try: empleado = request.user.empleado_perfil
    except: return redirect('inicio')
    if request.method == 'POST':
        form = AusenciaForm(request.POST)
        if form.is_valid(): a = form.save(commit=False); a.empleado = empleado; a.save(); messages.success(request, "Ausencia guardada."); return redirect('gestionar_ausencias')
    ausencias = Ausencia.objects.filter(empleado=empleado, fecha_fin__gte=timezone.now()).order_by('fecha_inicio')
    return render(request, 'salon/ausencias.html', {'form': AusenciaForm(), 'ausencias': ausencias})

@login_required
def eliminar_ausencia(request, ausencia_id):
    get_object_or_404(Ausencia, id=ausencia_id, empleado__user=request.user).delete(); return redirect('gestionar_ausencias')

def registro_empleado_publico(request, slug_peluqueria):
    peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)
    if request.method == 'POST':
        form = RegistroPublicoEmpleadoForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            if User.objects.filter(username=data['email']).exists(): return render(request, 'salon/registro_empleado.html', {'peluqueria': peluqueria, 'form': form, 'error': 'Correo ya registrado'})
            with transaction.atomic():
                u = User.objects.create_user(username=data['email'], email=data['email'], password=data['password'], first_name=data['nombre'], last_name=data['apellido']); u.perfil.peluqueria = peluqueria; u.perfil.es_dueño = False; u.perfil.save(); e = Empleado.objects.create(peluqueria=peluqueria, user=u, nombre=data['nombre'], apellido=data['apellido'], email_contacto=data['email'], activo=True)
                for i in range(7): HorarioEmpleado.objects.create(empleado=e, dia_semana=i, hora_inicio=time(9,0), hora_fin=time(19,0))
            login(request, u); return redirect('mi_agenda')
    return render(request, 'salon/registro_empleado.html', {'peluqueria': peluqueria, 'form': RegistroPublicoEmpleadoForm()})

def inicio(request): return render(request, 'salon/index.html', {'peluquerias': Peluqueria.objects.all(), 'ciudades': Peluqueria.objects.values_list('ciudad', flat=True).distinct()})

# ----------- LOGICA DE CITAS Y PAGOS -----------

def agendar_cita(request, slug_peluqueria):
    peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)
    
    # 1. Determinar si se obliga el pago digital
    tiene_bold = bool(peluqueria.bold_secret_key and peluqueria.bold_api_key)
    tiene_nequi = bool(peluqueria.nequi_celular)
    solo_pago_digital = tiene_bold or tiene_nequi
    
    if request.method == 'POST':
        try:
            emp_id = request.POST.get('empleado')
            fecha = request.POST.get('fecha_seleccionada')
            hora = request.POST.get('hora_seleccionada')
            servs_ids = request.POST.getlist('servicios')
            
            # Obtener metodo, si intentan hackear el form enviando SITIO cuando no deben, forzamos error
            metodo = request.POST.get('metodo_pago', 'SITIO')
            if solo_pago_digital and metodo == 'SITIO':
                raise ValueError("Debes seleccionar un método de pago digital.")
                
            tipo_cobro = request.POST.get('tipo_cobro', 'TOTAL')
            
            if not (emp_id and fecha and hora and servs_ids): raise ValueError("Datos incompletos")
            
            servs = Servicio.objects.filter(id__in=servs_ids)
            duracion = sum([s.duracion for s in servs], timedelta())
            precio = sum([s.precio for s in servs])
            
            ini = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
            
            def _reserva(emp):
                if Ausencia.objects.filter(empleado=emp, fecha_inicio__lt=ini + duracion, fecha_fin__gt=ini).exists(): 
                    raise ValueError("Estilista ausente")
                if Cita.objects.filter(empleado=emp, estado__in=['P','C'], fecha_hora_inicio__lt=ini + duracion, fecha_hora_fin__gt=ini).exists(): 
                    raise ValueError("Horario ocupado")
                
                c = Cita.objects.create(
                    peluqueria=peluqueria, 
                    empleado=emp, 
                    cliente_nombre=request.POST.get('nombre_cliente'), 
                    cliente_telefono=request.POST.get('telefono_cliente'), 
                    fecha_hora_inicio=ini, 
                    fecha_hora_fin=ini + duracion, 
                    precio_total=precio, 
                    estado='P', 
                    metodo_pago=metodo,
                    tipo_cobro=tipo_cobro
                )
                c.servicios.set(servs)
                return c
            
            cita = BookingManager.ejecutar_reserva_segura(emp_id, _reserva)
            
            if metodo == 'BOLD' and tiene_bold:
                return redirect('confirmacion_cita', slug_peluqueria=peluqueria.slug, cita_id=cita.id)
            
            elif metodo == 'NEQUI' and tiene_nequi:
                cita.enviar_notificacion_telegram()
                return render(request, 'salon/pago_nequi.html', {'cita': cita, 'peluqueria': peluqueria})
            
            else: # Pago en sitio
                cita.estado = 'C'
                cita.save()
                cita.enviar_notificacion_telegram()
                return render(request, 'salon/confirmacion.html', {'cita': cita})
                
        except Exception as e:
            return render(request, 'salon/agendar.html', {
                'peluqueria': peluqueria, 
                'servicios': peluqueria.servicios.all(), 
                'empleados': peluqueria.empleados.filter(activo=True), 
                'tiene_bold': tiene_bold,
                'tiene_nequi': tiene_nequi,
                'solo_pago_digital': solo_pago_digital,
                'error_mensaje': str(e)
            })
            
    return render(request, 'salon/agendar.html', {
        'peluqueria': peluqueria, 
        'servicios': peluqueria.servicios.all(), 
        'empleados': peluqueria.empleados.filter(activo=True), 
        'tiene_bold': tiene_bold, 
        'tiene_nequi': tiene_nequi,
        'solo_pago_digital': solo_pago_digital
    })

def confirmacion_cita(request, slug_peluqueria, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    peluqueria = cita.peluqueria
    
    # Validamos que tenga la API KEY configurada también
    if not (peluqueria.bold_secret_key and peluqueria.bold_api_key):
        return render(request, 'salon/confirmacion.html', {'cita': cita, 'mensaje': 'Pago en sitio'})
    
    monto_a_cobrar = cita.precio_total
    es_abono = False
    
    if cita.tipo_cobro == 'ABONO' and peluqueria.porcentaje_abono < 100:
        monto_a_cobrar = int(cita.precio_total * (peluqueria.porcentaje_abono/100))
        es_abono = True
        
    return render(request, 'salon/pago_bold.html', {
        'cita': cita,
        'peluqueria': peluqueria,
        'monto_a_cobrar': monto_a_cobrar,
        'es_abono': es_abono
    })

def procesar_pago_bold(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    peluqueria = cita.peluqueria
    
    # CORRECCIÓN: Usamos bold_api_key para la API de Links
    if not peluqueria.bold_api_key: 
        return render(request, 'salon/confirmacion.html', {'cita': cita, 'mensaje': 'Error de configuración en el comercio.'})
    
    try:
        monto = cita.precio_total
        desc = f"Reserva Cita #{cita.id}"
        
        if cita.tipo_cobro == 'ABONO' and peluqueria.porcentaje_abono < 100:
            monto = int(cita.precio_total * (peluqueria.porcentaje_abono/100))
            desc = f"Abono {peluqueria.porcentaje_abono}% Cita #{cita.id}"
            
        ref = f"CITA-{cita.id}-{int(datetime.now().timestamp())}"
        
        url = "https://integrations.api.bold.co/online/link/v1"
        
        # CORRECCIÓN: Header Authorization usa la api_key pública
        headers = {
            "Authorization": f"x-api-key {peluqueria.bold_api_key}", 
            "Content-Type": "application/json"
        }
        
        payload = {
            "name": desc, 
            "description": "Servicio de Belleza", 
            "amount": monto, 
            "currency": "COP", 
            "sku": ref, 
            "redirection_url": request.build_absolute_uri(reverse('retorno_bold'))
        }
        
        r = requests.post(url, json=payload, headers=headers, timeout=8)
        
        if r.status_code == 201:
            cita.referencia_pago = ref 
            cita.save()
            return redirect(r.json()["payload"]["url"])
        else:
            print(f"Bold Error: {r.status_code} {r.text}") 
            return render(request, 'salon/confirmacion.html', {'cita': cita, 'mensaje': 'No se pudo generar el link de pago. Intenta más tarde.'})
            
    except Exception as e:
        print(f"Bold Excepción: {e}") 
        return render(request, 'salon/confirmacion.html', {'cita': cita, 'mensaje': 'Error técnico. Contacta al salón.'})

def api_obtener_horarios(request):
    try: return JsonResponse({'horas': obtener_bloques_disponibles(Empleado.objects.get(id=request.GET.get('empleado_id')), datetime.strptime(request.GET.get('fecha'), '%Y-%m-%d').date(), timedelta(minutes=30))})
    except: return JsonResponse({'horas': []})

def retorno_bold(request): 
    payment_status = request.GET.get('payment_status')
    if payment_status == 'APPROVED':
        return render(request, 'salon/confirmacion.html', {'mensaje': '¡Pago Exitoso! Tu cita ha sido confirmada.'})
    else:
        return render(request, 'salon/confirmacion.html', {'mensaje': 'El pago no fue aprobado o fue cancelado.'})
'''

# --- CONTENIDO 3: salon/templates/salon/agendar.html ---
agendar_html_code = r'''{% load static %}
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Reserva | {{ peluqueria.nombre_visible }}</title>
    
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700&display=swap" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    
    <style>
        :root { --primary: #1e293b; --accent: #db2777; --bg: #f8fafc; }
        body { font-family: 'Manrope', sans-serif; background: var(--bg); color: var(--primary); margin: 0; padding-bottom: 80px; }
        .header { background: white; padding: 20px; text-align: center; border-radius: 0 0 30px 30px; box-shadow: 0 4px 20px rgba(0,0,0,0.05); }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .card { background: white; border-radius: 16px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.03); border: 1px solid #e2e8f0; cursor: pointer; transition: 0.2s; }
        .card.selected { border-color: var(--accent); background: #fdf2f8; }
        .input-fancy { width: 100%; padding: 15px; border: 1px solid #cbd5e1; border-radius: 12px; font-size: 1rem; margin-bottom: 15px; box-sizing: border-box; }
        .btn-main { width: 100%; padding: 18px; background: var(--primary); color: white; border: none; border-radius: 50px; font-size: 1.1rem; font-weight: bold; cursor: pointer; position: fixed; bottom: 0; left: 0; border-radius: 0; z-index: 100; }
        .btn-main:disabled { background: #cbd5e1; }
        .hidden { display: none; }
        
        .pay-grid { display: grid; grid-template-columns: 1fr; gap: 10px; margin-top: 10px; }
        .pay-option { border: 1px solid #e2e8f0; padding: 15px; border-radius: 12px; display: flex; align-items: center; gap: 15px; cursor: pointer; background: white; }
        .pay-option.selected { border-color: var(--accent); background: #fdf2f8; color: var(--accent); font-weight: bold; }
        .pay-option i { font-size: 1.5rem; }

        /* Opciones de Cobro */
        .cobro-options { display: flex; gap: 10px; margin-top: 15px; display: none; }
        .cobro-option { flex: 1; padding: 10px; border: 1px solid #e2e8f0; border-radius: 8px; text-align: center; cursor: pointer; font-size: 0.9rem; }
        .cobro-option.active { background: var(--accent); color: white; border-color: var(--accent); }

        .price-summary { margin-top: 20px; padding: 15px; background: #fff1f2; border-radius: 12px; text-align: center; }
        .total-price { font-size: 1.5rem; font-weight: bold; color: var(--accent); }
        .error-msg { background: #fee2e2; color: #b91c1c; padding: 10px; border-radius: 8px; margin-bottom: 15px; text-align: center; }
    </style>
</head>
<body>

    <div class="header">
        <h1 style="margin:0; font-size: 1.8rem;">{{ peluqueria.nombre_visible }}</h1>
        <p style="margin:5px 0; color: #64748b;">
            {% if peluqueria.esta_abierto %}
                <span style="color: green;">● Abierto ahora</span>
            {% else %}
                <span style="color: red;">● Cerrado ahora</span>
            {% endif %}
        </p>
    </div>

    <div class="container">
        {% if error_mensaje %}
            <div class="error-msg">{{ error_mensaje }}</div>
        {% endif %}

        <form method="POST" id="bookingForm">
            {% csrf_token %}
            <input type="hidden" name="fecha_seleccionada" id="input_fecha">
            <input type="hidden" name="hora_seleccionada" id="input_hora">
            <input type="hidden" name="empleado" id="input_empleado">
            
            <input type="hidden" name="metodo_pago" id="input_metodo_pago" value="">
            <input type="hidden" name="tipo_cobro" id="input_tipo_cobro" value="TOTAL">

            <h3>1. Elige Servicio</h3>
            {% for s in servicios %}
            <div class="card" onclick="toggleService(this, {{ s.precio }})">
                <input type="checkbox" name="servicios" value="{{ s.id }}" class="hidden check-servicio">
                <div style="display:flex; justify-content:space-between; font-weight:bold;">
                    <span>{{ s.nombre }}</span>
                    <span>${{ s.precio }}</span>
                </div>
                <small style="color:#64748b;">{{ s.str_duracion }}</small>
            </div>
            {% endfor %}

            <div id="step-empleado" class="hidden">
                <h3>2. Elige Profesional</h3>
                <div style="display:flex; gap:10px; overflow-x:auto; padding-bottom:10px;">
                    {% for e in empleados %}
                    <div class="card" style="min-width:100px; text-align:center;" onclick="selectStylist(this, '{{ e.id }}')">
                        <div style="width:50px; height:50px; background:#e2e8f0; border-radius:50%; margin:0 auto 10px; display:flex; align-items:center; justify-content:center; font-weight:bold;">
                            {{ e.nombre|first }}
                        </div>
                        <span>{{ e.nombre }}</span>
                    </div>
                    {% endfor %}
                </div>
            </div>

            <div id="step-fecha" class="hidden">
                <h3>3. Fecha y Hora</h3>
                <input type="date" id="picker-fecha" class="input-fancy" required>
                <div id="loading" class="hidden" style="text-align:center; color:#64748b;">Buscando disponibilidad...</div>
                <div id="contenedor-horas" style="display:grid; grid-template-columns: repeat(4, 1fr); gap:10px;"></div>
            </div>

            <div id="step-datos" class="hidden">
                <h3>4. Tus Datos</h3>
                <input type="text" name="nombre_cliente" class="input-fancy" placeholder="Tu Nombre" required>
                <input type="tel" name="telefono_cliente" class="input-fancy" placeholder="WhatsApp (10 dígitos)" pattern="[0-9]{10}" required>

                <h3>Forma de Pago</h3>
                <div class="pay-grid">
                    {% if tiene_bold %}
                    <div class="pay-option" id="opt-bold" onclick="setPago(this, 'BOLD')">
                        <i class="fas fa-credit-card" style="color:#db2777;"></i>
                        <div>
                            <strong>Pago Seguro (Tarjetas/PSE)</strong><br>
                            <small>Bold</small>
                        </div>
                    </div>
                    {% endif %}
                    
                    {% if tiene_nequi %}
                    <div class="pay-option" id="opt-nequi" onclick="setPago(this, 'NEQUI')">
                        <i class="fas fa-mobile-alt"></i> Nequi
                    </div>
                    {% endif %}
                    
                    {% if not solo_pago_digital %}
                    <div class="pay-option selected" id="opt-sitio" onclick="setPago(this, 'SITIO')">
                        <i class="fas fa-store"></i> Pagar en el Salón
                    </div>
                    {% endif %}
                </div>

                <div id="opciones-cobro" class="cobro-options">
                    <div class="cobro-option active" onclick="setTipoCobro('TOTAL', this)">
                        Pagar Total<br>
                        <strong id="label-total">$0</strong>
                    </div>
                    {% if peluqueria.porcentaje_abono < 100 %}
                    <div class="cobro-option" onclick="setTipoCobro('ABONO', this)">
                        Abonar {{ peluqueria.porcentaje_abono }}%<br>
                        <strong id="label-abono">$0</strong>
                    </div>
                    {% endif %}
                </div>

                <div class="price-summary">
                    Total a pagar ahora: <div class="total-price" id="final-price">$0</div>
                </div>

                <p style="font-size:0.8rem; color:#64748b; margin-top:10px; text-align: center;">
                    * Al reservar aceptas nuestras políticas de cancelación.
                </p>
            </div>

            <button type="submit" class="btn-main" id="btn-submit" disabled>CONFIRMAR RESERVA</button>
        </form>
    </div>

    <script>
        const pickerFecha = document.getElementById('picker-fecha');
        pickerFecha.min = new Date().toISOString().split('T')[0];
        let totalServicios = 0;
        const porcentajeAbono = {{ peluqueria.porcentaje_abono }};

        // Autoselección de método de pago al cargar
        document.addEventListener("DOMContentLoaded", function() {
            const sitio = document.getElementById('opt-sitio');
            const bold = document.getElementById('opt-bold');
            const nequi = document.getElementById('opt-nequi');
            
            // Si la opción de sitio no existe (porque es pago digital obligatorio)
            if (!sitio) {
                if (bold) {
                    setPago(bold, 'BOLD');
                } else if (nequi) {
                    setPago(nequi, 'NEQUI');
                }
            } else {
                // Si existe sitio, es el default
                setPago(sitio, 'SITIO'); 
            }
        });

        function toggleService(card, precio) {
            const chk = card.querySelector('input');
            chk.checked = !chk.checked;
            card.classList.toggle('selected', chk.checked);
            if(chk.checked) totalServicios += precio; else totalServicios -= precio;
            updatePrices(); checkVisibility();
        }

        function updatePrices() {
            const abono = Math.round(totalServicios * (porcentajeAbono / 100));
            document.getElementById('label-total').innerText = '$' + totalServicios.toLocaleString();
            const labelAbono = document.getElementById('label-abono');
            if(labelAbono) labelAbono.innerText = '$' + abono.toLocaleString();
            const tipo = document.getElementById('input_tipo_cobro').value;
            const final = (tipo === 'TOTAL') ? totalServicios : abono;
            document.getElementById('final-price').innerText = '$' + final.toLocaleString();
        }

        function selectStylist(card, id) {
            document.querySelectorAll('#step-empleado .card').forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
            document.getElementById('input_empleado').value = id;
            document.getElementById('step-fecha').classList.remove('hidden');
            pickerFecha.scrollIntoView({behavior:'smooth'});
        }

        pickerFecha.addEventListener('change', async () => {
            const fecha = pickerFecha.value;
            const emp = document.getElementById('input_empleado').value;
            const servs = Array.from(document.querySelectorAll('.check-servicio:checked')).map(c => c.value);
            document.getElementById('input_fecha').value = fecha;
            document.getElementById('loading').classList.remove('hidden');
            document.getElementById('contenedor-horas').innerHTML = '';
            
            // Fetch a la API con la fecha seleccionada
            const res = await fetch(`/api/horarios/?empleado_id=${emp}&fecha=${fecha}&s=${servs.join(',')}`);
            const data = await res.json();
            
            document.getElementById('loading').classList.add('hidden');
            const cont = document.getElementById('contenedor-horas');
            
            if(data.horas.length === 0) {
                cont.innerHTML = '<div style="grid-column:1/-1; text-align:center;">No hay cupos disponibles.</div>'; return;
            }
            data.horas.forEach(h => {
                const btn = document.createElement('div');
                btn.className = 'card';
                btn.style.textAlign = 'center';
                btn.style.marginBottom = '0';
                btn.textContent = h;
                btn.onclick = () => {
                    document.querySelectorAll('#contenedor-horas div').forEach(d => d.classList.remove('selected'));
                    btn.classList.add('selected');
                    document.getElementById('input_hora').value = h;
                    document.getElementById('step-datos').classList.remove('hidden');
                    document.getElementById('btn-submit').disabled = false;
                    setTimeout(() => document.getElementById('step-datos').scrollIntoView({behavior:'smooth'}), 100);
                };
                cont.appendChild(btn);
            });
        });

        function setPago(elem, metodo) {
            document.querySelectorAll('.pay-option').forEach(e => e.classList.remove('selected'));
            elem.classList.add('selected');
            document.getElementById('input_metodo_pago').value = metodo;
            const divOpciones = document.getElementById('opciones-cobro');
            if (metodo === 'BOLD') {
                divOpciones.style.display = 'flex'; 
                // Seleccionar Total por defecto al cambiar a Bold
                const optTotal = divOpciones.querySelector('.cobro-option');
                if(optTotal) setTipoCobro('TOTAL', optTotal);
            } else {
                divOpciones.style.display = 'none'; 
                setTipoCobro('TOTAL', null);
            }
            updatePrices();
        }

        function setTipoCobro(tipo, elem) {
            document.getElementById('input_tipo_cobro').value = tipo;
            if(elem) {
                document.querySelectorAll('.cobro-option').forEach(e => e.classList.remove('active'));
                elem.classList.add('active');
            }
            updatePrices();
        }

        function checkVisibility() {
            if(document.querySelectorAll('.check-servicio:checked').length > 0) document.getElementById('step-empleado').classList.remove('hidden');
            else document.getElementById('step-empleado').classList.add('hidden');
        }
    </script>
</body>
</html>
'''

# Mapa de archivos a escribir
archivos = {
    "salon/services.py": services_code,
    "salon/views.py": views_code,
    "salon/templates/salon/agendar.html": agendar_html_code
}

for ruta, contenido in archivos.items():
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(contenido)
        print(f"✅ Archivo actualizado correctamente: {ruta}")
    except Exception as e:
        print(f"❌ Error al escribir {ruta}: {e}")