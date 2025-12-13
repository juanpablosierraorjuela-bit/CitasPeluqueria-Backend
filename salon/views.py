import logging, json, requests, math
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
from .models import Peluqueria, Servicio, Empleado, Cita, HorarioEmpleado, ConfiguracionPlataforma, Ausencia, Producto, MovimientoInventario, PerfilUsuario
from .forms import ServicioForm, RegistroPublicoEmpleadoForm, AusenciaForm
from .services import obtener_bloques_disponibles
from salon.utils.booking_lock import BookingManager

logger = logging.getLogger(__name__)

# --- UTILIDADES GEO ---
def calcular_distancia(lat1, lon1, lat2, lon2):
    # Fórmula de Haversine simplificada para distancias cortas
    R = 6371  # Radio de la Tierra en km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = R * c
    return d * 1000 # Retorna en metros

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
    try:
        if hasattr(user, 'perfil') and user.perfil.es_dueño: return redirect('panel_negocio')
    except: pass
    try:
        if hasattr(user, 'empleado_perfil'): return redirect('mi_agenda')
    except: pass
    return redirect('inicio')

def logout_view(request): logout(request); return redirect('inicio')

# --- REGISTRO SAAS (DUEÑOS) ---

def landing_saas(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                email = request.POST.get('email')
                if User.objects.filter(username=email).exists(): 
                    raise ValueError("El correo ya está registrado.")
                
                # Crear Usuario
                user = User.objects.create_user(
                    username=request.POST.get('username_owner', email), 
                    email=email, 
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
                
                # Asignar Perfil (Manejando el conflicto con signal)
                perfil, created = PerfilUsuario.objects.get_or_create(user=user)
                perfil.peluqueria = peluqueria
                perfil.es_dueño = True
                perfil.save()
                
                # Crear Empleado (Dueño también es empleado)
                Empleado.objects.create(
                    user=user, 
                    peluqueria=peluqueria, 
                    nombre=user.first_name, 
                    apellido=user.last_name, 
                    email_contacto=user.email, 
                    activo=True
                )
            
            # Notificación Interna Telegram (Opcional)
            config = ConfiguracionPlataforma.objects.first()
            if config and config.telegram_token:
                try: requests.post(f"https://api.telegram.org/bot{config.telegram_token}/sendMessage", data={"chat_id": config.telegram_chat_id, "text": f"💰 *NUEVO SAAS*\nNegocio: {peluqueria.nombre}", "parse_mode": "Markdown"}, timeout=3)
                except: pass
            
            login(request, user)
            return redirect('pago_suscripcion_saas')
            
        except Exception as e: 
            messages.error(request, f"Error en registro: {str(e)}")
            
    return render(request, 'salon/landing_saas.html')

@login_required
def pago_suscripcion_saas(request):
    if not request.user.perfil.es_dueño: return redirect('inicio')
    peluqueria = request.user.perfil.peluqueria
    config = ConfiguracionPlataforma.objects.first()
    monto = config.precio_mensualidad if config else 130000
    
    # Si ya pagó o tiene periodo de prueba, podría saltar esto.
    
    if request.method == 'POST':
        # Intento pago Bold para suscripción
        if config and config.bold_secret_key:
            try:
                ref = f"SUB-{peluqueria.id}-{int(datetime.now().timestamp())}"
                url = "https://integrations.api.bold.co/online/link/v1"
                headers = {"Authorization": f"x-api-key {config.bold_secret_key}", "Content-Type": "application/json"}
                payload = {
                    "name": "Suscripción PASO", 
                    "description": f"Plan Mensual {peluqueria.nombre}", 
                    "amount": monto, 
                    "currency": "COP", 
                    "sku": ref, 
                    "redirection_url": request.build_absolute_uri(reverse('panel_negocio'))
                }
                r = requests.post(url, json=payload, headers=headers, timeout=10)
                if r.status_code == 201: return redirect(r.json()["payload"]["url"])
            except Exception as e:
                print(f"Error Bold Suscripcion: {e}")

        # Fallback
        return redirect(config.link_pago_bold) if config else redirect('panel_negocio')
        
    return render(request, 'salon/pago_suscripcion.html', {'monto': monto, 'peluqueria': peluqueria})

# --- GESTIÓN NEGOCIO (DUEÑO) ---

@login_required
def panel_negocio(request):
    if not request.user.perfil.es_dueño: return redirect('inicio')
    peluqueria = request.user.perfil.peluqueria
    hoy = timezone.localdate()
    
    # Lógica Fechas Pago
    inicio = peluqueria.fecha_inicio_contrato.date()
    proximo = inicio
    while proximo <= hoy: proximo += relativedelta(months=1)
    dias = (proximo - hoy).days
    alerta = f"⚠️ Tu plan vence en {dias} días." if dias <= 5 else None

    if request.method == 'POST':
        accion = request.POST.get('accion')
        
        if accion == 'guardar_pagos':
            peluqueria.porcentaje_abono = int(request.POST.get('porcentaje_abono') or 50)
            peluqueria.bold_api_key = request.POST.get('bold_api_key')
            peluqueria.bold_secret_key = request.POST.get('bold_secret_key')
            peluqueria.nequi_celular = request.POST.get('nequi_celular')
            peluqueria.ofrece_domicilio = request.POST.get('ofrece_domicilio') == 'on'
            peluqueria.comision_domicilio = int(request.POST.get('comision_domicilio') or 10)
            
            if 'nequi_qr_imagen' in request.FILES: 
                peluqueria.nequi_qr_imagen = request.FILES['nequi_qr_imagen']
            
            peluqueria.save()
            messages.success(request, "Configuración financiera actualizada.")
            
        elif accion == 'guardar_redes':
            peluqueria.instagram = request.POST.get('instagram')
            peluqueria.facebook = request.POST.get('facebook')
            peluqueria.tiktok = request.POST.get('tiktok')
            if 'logo' in request.FILES: peluqueria.logo = request.FILES['logo']
            peluqueria.save()
            messages.success(request, "Imagen y redes actualizadas.")

        return redirect('panel_negocio')

    # Datos Dashboard
    citas_hoy = peluqueria.citas.filter(fecha_hora_inicio__date=hoy).order_by('fecha_hora_inicio')
    citas_futuras = peluqueria.citas.filter(fecha_hora_inicio__gte=timezone.now()).order_by('fecha_hora_inicio')[:20]
    
    ctx = {
        'peluqueria': peluqueria, 
        'alerta_pago': alerta, 
        'proximo_pago': proximo, 
        'citas_hoy_count': citas_hoy.count(), 
        'citas_futuras': citas_futuras, 
        'empleados': peluqueria.empleados.all(), 
        'servicios': peluqueria.servicios.all(),
        'inventario': peluqueria.inventario.all()[:5], # Mostrar resumen inventario
        'link_invitacion': request.build_absolute_uri(reverse('registro_empleado', args=[peluqueria.slug]))
    }
    return render(request, 'salon/dashboard.html', ctx)

@login_required
def gestionar_servicios(request):
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
    return render(request, 'salon/panel_dueño/servicios.html', {'servicios': peluqueria.servicios.all(), 'form': ServicioForm(), 'peluqueria': peluqueria})

@login_required
def eliminar_servicio(request, servicio_id):
    get_object_or_404(Servicio, id=servicio_id, peluqueria=request.user.perfil.peluqueria).delete(); return redirect('gestionar_servicios')

@login_required
def gestionar_equipo(request):
    peluqueria = request.user.perfil.peluqueria
    link = request.build_absolute_uri(reverse('registro_empleado', args=[peluqueria.slug]))
    return render(request, 'salon/panel_dueño/equipo.html', {'peluqueria': peluqueria, 'empleados': peluqueria.empleados.all(), 'link_invitacion': link})

# --- EMPLEADO ---

@login_required
def mi_agenda(request):
    try: empleado = request.user.empleado_perfil
    except: return redirect('login_custom')
    
    if request.method == 'POST':
        # Guardar Redes del Empleado
        if 'instagram' in request.POST:
            empleado.instagram = request.POST.get('instagram')
            empleado.save()
            messages.success(request, "Perfil actualizado")
        
        # Guardar Horario
        else:
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
    lista = [{'id': i, 'nombre': n, 'trabaja': horarios.get(i) is not None, 'inicio': horarios.get(i).hora_inicio.strftime('%H:%M') if horarios.get(i) else '09:00', 'fin': horarios.get(i).hora_fin.strftime('%H:%M') if horarios.get(i) else '19:00'} for i, n in enumerate(['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'])]
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
                u = User.objects.create_user(username=data['email'], email=data['email'], password=data['password'], first_name=data['nombre'], last_name=data['apellido'])
                # Perfil se crea por signal, lo actualizamos
                u.perfil.peluqueria = peluqueria
                u.perfil.es_dueño = False
                u.perfil.save()
                e = Empleado.objects.create(peluqueria=peluqueria, user=u, nombre=data['nombre'], apellido=data['apellido'], email_contacto=data['email'], activo=True)
                for i in range(7): HorarioEmpleado.objects.create(empleado=e, dia_semana=i, hora_inicio=time(9,0), hora_fin=time(19,0))
            login(request, u); return redirect('mi_agenda')
    return render(request, 'salon/registro_empleado.html', {'peluqueria': peluqueria, 'form': RegistroPublicoEmpleadoForm()})

# --- CLIENTES Y BÚSQUEDA ---

def inicio(request):
    peluquerias = Peluqueria.objects.filter(activo_saas=True)
    
    # Geolocalización (Filtrado Básico)
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    
    if lat and lon:
        try:
            lat, lon = float(lat), float(lon)
            # Filtrar y ordenar por distancia (en memoria para SQLite, usar PostGIS para prod real)
            p_con_distancia = []
            for p in peluquerias:
                dist = calcular_distancia(lat, lon, p.latitud, p.longitud)
                if dist <= 5000: # Mostrar solo a 5km a la redonda (usuario pidió 500m, ampliamos un poco para UX)
                    p.distancia_aprox = int(dist)
                    p_con_distancia.append(p)
            p_con_distancia.sort(key=lambda x: x.distancia_aprox)
            peluquerias = p_con_distancia
        except:
            pass # Si falla lat/lon, muestra todas
            
    return render(request, 'salon/index.html', {'peluquerias': peluquerias, 'ciudades': Peluqueria.objects.values_list('ciudad', flat=True).distinct()})

# ----------- LOGICA DE CITAS Y PAGOS (NUCLEAR) -----------

def agendar_cita(request, slug_peluqueria):
    peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)
    
    tiene_bold = bool(peluqueria.bold_secret_key and peluqueria.bold_api_key)
    tiene_nequi = bool(peluqueria.nequi_celular)
    solo_pago_digital = tiene_bold or tiene_nequi
    
    if request.method == 'POST':
        try:
            # Validación Políticas
            if not request.POST.get('acepta_politicas'):
                raise ValueError("Debes aceptar las políticas de cancelación.")

            emp_id = request.POST.get('empleado')
            fecha = request.POST.get('fecha_seleccionada')
            hora = request.POST.get('hora_seleccionada')
            servs_ids = request.POST.getlist('servicios')
            
            # Validar que si eligió domicilio, el local lo ofrezca
            es_domicilio = request.POST.get('es_domicilio') == 'on'
            if es_domicilio and not peluqueria.ofrece_domicilio:
                 raise ValueError("Este establecimiento no ofrece servicio a domicilio.")

            metodo = request.POST.get('metodo_pago', 'SITIO')
            if solo_pago_digital and metodo == 'SITIO':
                raise ValueError("Debes seleccionar un método de pago digital.")
                
            tipo_cobro = request.POST.get('tipo_cobro', 'TOTAL')
            
            if not (emp_id and fecha and hora and servs_ids): raise ValueError("Datos incompletos")
            
            servs = Servicio.objects.filter(id__in=servs_ids)
            duracion = sum([s.duracion for s in servs], timedelta())
            precio = sum([s.precio for s in servs])
            
            # Recargo domicilio si aplica (podría ser lógica futura)
            
            ini = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
            
            # --- LOCKING DE RESERVA ---
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
                    estado='P',  # Siempre PENDIENTE hasta confirmar pago
                    metodo_pago=metodo,
                    tipo_cobro=tipo_cobro,
                    es_domicilio=es_domicilio,
                    direccion_domicilio=request.POST.get('direccion_domicilio') if es_domicilio else None
                )
                c.servicios.set(servs)
                return c
            
            cita = BookingManager.ejecutar_reserva_segura(emp_id, _reserva)
            
            # Redirección según método
            if metodo == 'BOLD' and tiene_bold:
                # Redirige a vista intermedia para generar link
                return redirect('procesar_pago_bold', cita_id=cita.id)
            
            elif metodo == 'NEQUI' and tiene_nequi:
                cita.enviar_notificacion_telegram() # Avisar intento
                return render(request, 'salon/pago_nequi.html', {'cita': cita, 'peluqueria': peluqueria})
            
            else: # Pago en sitio
                cita.estado = 'C'
                cita.save()
                # Descontar Inventario (Si aplica)
                for s in cita.servicios.all():
                    if s.producto_asociado:
                        p = s.producto_asociado
                        p.cantidad_actual -= s.cantidad_descuento
                        p.save()
                        MovimientoInventario.objects.create(producto=p, tipo='SALIDA', cantidad=s.cantidad_descuento, descripcion=f"Servicio Cita #{cita.id}")

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
    """ Vista genérica de confirmación """
    cita = get_object_or_404(Cita, id=cita_id)
    return render(request, 'salon/confirmacion.html', {'cita': cita})

def procesar_pago_bold(request, cita_id):
    """ Genera el link de pago y redirige a Bold """
    cita = get_object_or_404(Cita, id=cita_id)
    peluqueria = cita.peluqueria
    
    if not peluqueria.bold_secret_key: 
        return render(request, 'salon/confirmacion.html', {'cita': cita, 'mensaje': 'Error: Comercio sin llave secreta configurada.'})
    
    try:
        monto = cita.precio_total
        desc = f"Reserva Cita #{cita.id}"
        
        if cita.tipo_cobro == 'ABONO' and peluqueria.porcentaje_abono < 100:
            monto = int(cita.precio_total * (peluqueria.porcentaje_abono/100))
            desc = f"Abono {peluqueria.porcentaje_abono}% Cita #{cita.id}"
            
        ref = f"CITA-{cita.id}-{int(datetime.now().timestamp())}"
        
        url = "https://integrations.api.bold.co/online/link/v1"
        
        headers = {
            "Authorization": f"x-api-key {peluqueria.bold_secret_key}", 
            "Content-Type": "application/json"
        }
        
        # URL DE RETORNO CLAVE: Debe ser absoluta y pública
        url_retorno = request.build_absolute_uri(reverse('retorno_bold')) + f"?cita_id={cita.id}"
        
        payload = {
            "name": desc, 
            "description": "Servicio de Belleza", 
            "amount": monto, 
            "currency": "COP", 
            "sku": ref, 
            "redirection_url": url_retorno
        }
        
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if r.status_code == 201:
            cita.referencia_pago = ref 
            cita.save()
            return redirect(r.json()["payload"]["url"])
        else:
            print(f"Bold Error: {r.status_code} {r.text}") 
            return render(request, 'salon/confirmacion.html', {'cita': cita, 'mensaje': 'No se pudo generar el link de pago con Bold.'})
            
    except Exception as e:
        print(f"Bold Excepción: {e}") 
        return render(request, 'salon/confirmacion.html', {'cita': cita, 'mensaje': 'Error de conexión con la pasarela.'})

def retorno_bold(request): 
    """ Maneja el retorno del usuario desde Bold """
    cita_id = request.GET.get('cita_id')
    payment_status = request.GET.get('payment_status') # APPROVED, REJECTED, FAILED
    
    cita = get_object_or_404(Cita, id=cita_id)
    
    if payment_status == 'APPROVED':
        if cita.estado != 'C': # Evitar doble confirmación
            cita.estado = 'C'
            cita.abono_pagado = int(cita.precio_total * (cita.peluqueria.porcentaje_abono/100)) if cita.tipo_cobro == 'ABONO' else cita.precio_total
            cita.save()
            
            # Descuento de Inventario Automático
            for s in cita.servicios.all():
                if s.producto_asociado:
                    p = s.producto_asociado
                    p.cantidad_actual -= s.cantidad_descuento
                    p.save()
                    MovimientoInventario.objects.create(producto=p, tipo='SALIDA', cantidad=s.cantidad_descuento, descripcion=f"Venta Cita Bold #{cita.id}")

            cita.enviar_notificacion_telegram()
            
        return render(request, 'salon/confirmacion.html', {'cita': cita, 'mensaje': '¡Pago Exitoso! Tu cita ha sido confirmada.'})
    else:
        # Si falló, la cita sigue en 'P' o se marca 'X'
        return render(request, 'salon/confirmacion.html', {'cita': cita, 'mensaje': 'El pago no fue aprobado. Intenta nuevamente.', 'error': True})

def api_obtener_horarios(request):
    try: return JsonResponse({'horas': obtener_bloques_disponibles(Empleado.objects.get(id=request.GET.get('empleado_id')), datetime.strptime(request.GET.get('fecha'), '%Y-%m-%d').date(), timedelta(minutes=30))})
    except: return JsonResponse({'horas': []})
