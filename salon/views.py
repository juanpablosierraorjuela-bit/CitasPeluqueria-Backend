# UBICACIÓN: salon/views.py
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.contrib import messages
from datetime import timedelta, time, datetime
from django.utils import timezone
import json

# Importaciones locales
from .models import Peluqueria, Servicio, Empleado, Cita, PerfilUsuario, HorarioEmpleado
# Nota: ConfigNegocioForm se eliminó porque hacemos el guardado manual para mayor control en este caso
from .forms import ServicioForm, RegistroPublicoEmpleadoForm
from .services import obtener_bloques_disponibles
from salon.utils.booking_lock import BookingManager

# Configurar Logger para ver errores en la consola de Render
logger = logging.getLogger(__name__)

# =======================================================
# 1. AUTENTICACIÓN Y REGISTRO
# =======================================================

def login_custom(request):
    """Login centralizado que redirige según el rol"""
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
    if user.is_superuser:
        return redirect('/admin/') # Tú vas al Django Admin
    
    # Verificar si es dueño
    try:
        if hasattr(user, 'perfil') and user.perfil.es_dueño:
            return redirect('panel_negocio')
    except: pass

    # Verificar si es empleado
    try:
        if hasattr(user, 'empleado_perfil'):
            return redirect('mi_agenda')
    except: pass
        
    return redirect('inicio')

def logout_view(request):
    logout(request)
    return redirect('login_custom')

def registro_empleado_publico(request, slug_peluqueria):
    """Permite que un empleado se registre solo mediante un link"""
    peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)

    if request.method == 'POST':
        form = RegistroPublicoEmpleadoForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            
            if User.objects.filter(username=data['email']).exists():
                return render(request, 'salon/registro_empleado.html', {'peluqueria': peluqueria, 'form': form, 'error': 'Ese correo ya está registrado.'})

            try:
                with transaction.atomic():
                    # 1. Crear Usuario
                    user = User.objects.create_user(username=data['email'], email=data['email'], password=data['password'])
                    user.first_name = data['nombre']
                    user.last_name = data['apellido']
                    user.save()

                    # 2. Crear Perfil (NO es dueño)
                    PerfilUsuario.objects.create(user=user, peluqueria=peluqueria, es_dueño=False)

                    # 3. Crear Ficha Empleado
                    emp = Empleado.objects.create(
                        peluqueria=peluqueria, user=user,
                        nombre=data['nombre'], apellido=data['apellido'],
                        email_contacto=data['email'], activo=True
                    )

                    # 4. Horarios Default
                    for i in range(7):
                        HorarioEmpleado.objects.create(empleado=emp, dia_semana=i, hora_inicio=time(9,0), hora_fin=time(19,0))

                # Auto-login y redirigir
                login(request, user)
                return redirect('mi_agenda')

            except Exception as e:
                logger.error(f"Error registrando empleado: {e}")
                return render(request, 'salon/registro_empleado.html', {'peluqueria': peluqueria, 'form': form, 'error': 'Error interno al crear cuenta.'})
    else:
        form = RegistroPublicoEmpleadoForm()

    return render(request, 'salon/registro_empleado.html', {'peluqueria': peluqueria, 'form': form})

# =======================================================
# 2. PANEL DEL DUEÑO (DASHBOARD)
# =======================================================

@login_required
def panel_negocio(request):
    if not hasattr(request.user, 'perfil') or not request.user.perfil.es_dueño:
        return redirect('inicio')
    
    peluqueria = request.user.perfil.peluqueria
    hoy = timezone.localdate()
    
    # KPIs Básicos
    citas_hoy = peluqueria.citas.filter(fecha_hora_inicio__date=hoy).count()
    empleados = peluqueria.empleados.filter(activo=True)
    servicios = peluqueria.servicios.all()

    # KPIs Avanzados
    ingresos_mes = peluqueria.citas.filter(
        fecha_hora_inicio__month=hoy.month, 
        estado='C'
    ).aggregate(Sum('precio_total'))['precio_total__sum'] or 0

    proximas_citas = peluqueria.citas.filter(
        fecha_hora_inicio__gte=timezone.now(),
        estado__in=['C', 'P']
    ).order_by('fecha_hora_inicio')[:10]

    return render(request, 'salon/panel_dueño/inicio.html', {
        'peluqueria': peluqueria, 
        'citas_hoy': citas_hoy, 
        'empleados': empleados, 
        'servicios': servicios,
        'ingresos_mes': ingresos_mes,
        'proximas_citas': proximas_citas
    })

@login_required
def configuracion_negocio(request):
    """
    Vista protegida para guardar tokens de Bold y Telegram.
    Maneja errores y genera Logs en caso de fallo.
    """
    # 1. Validación de seguridad básica
    if not hasattr(request.user, 'perfil') or not request.user.perfil.es_dueño:
        messages.error(request, "No tienes permisos de dueño para acceder aquí.")
        return redirect('inicio')

    if not request.user.perfil.peluqueria:
        messages.error(request, "Tu usuario no tiene una peluquería asignada.")
        return redirect('panel_negocio')
    
    peluqueria = request.user.perfil.peluqueria

    # 2. Procesamiento del Formulario (POST)
    if request.method == 'POST':
        try:
            # Captura de datos con .get() para evitar KeyErrors
            peluqueria.bold_api_key = request.POST.get('bold_api_key', '').strip()
            peluqueria.bold_integrity_key = request.POST.get('bold_integrity_key', '').strip()
            peluqueria.bold_secret_key = request.POST.get('bold_secret_key', '').strip()
            peluqueria.telegram_token = request.POST.get('telegram_token', '').strip()
            peluqueria.telegram_chat_id = request.POST.get('telegram_chat_id', '').strip()
            
            peluqueria.save()
            messages.success(request, "¡Configuración guardada exitosamente!")
            
        except Exception as e:
            # Registrar el error real en los logs de Render
            logger.error(f"[ERROR CONFIGURACION] Fallo al guardar datos peluqueria ID {peluqueria.id}: {str(e)}")
            messages.error(request, f"Hubo un error al guardar: {str(e)}")

    # 3. Generación de URL Webhook para mostrar en pantalla
    # Usamos try/except por si request.build_absolute_uri falla en algunos contextos (raro, pero preventivo)
    try:
        webhook_url = request.build_absolute_uri('/webhooks/bold/') 
    except Exception:
        webhook_url = "/webhooks/bold/ (Error generando URL absoluta)"
    
    return render(request, 'negocio/configuracion.html', {
        'peluqueria': peluqueria,
        'webhook_url': webhook_url
    })

@login_required
def gestionar_servicios(request):
    if not hasattr(request.user, 'perfil') or not request.user.perfil.es_dueño:
        return redirect('inicio')
        
    peluqueria = request.user.perfil.peluqueria
    
    if request.method == 'POST':
        form = ServicioForm(request.POST)
        if form.is_valid():
            try:
                nuevo = form.save(commit=False)
                nuevo.peluqueria = peluqueria
                nuevo.duracion = timedelta(minutes=form.cleaned_data['duracion_minutos'])
                nuevo.save()
                messages.success(request, "Servicio creado exitosamente.")
                return redirect('gestionar_servicios')
            except Exception as e:
                logger.error(f"Error creando servicio: {e}")
                messages.error(request, "Error al guardar el servicio.")
    else:
        form = ServicioForm()

    servicios = peluqueria.servicios.all()
    
    return render(request, 'salon/panel_dueño/servicios.html', {
        'servicios': servicios, 
        'form': form, 
        'peluqueria': peluqueria
    })

@login_required
def eliminar_servicio(request, servicio_id):
    if not hasattr(request.user, 'perfil') or not request.user.perfil.es_dueño:
        return redirect('inicio')
        
    s = get_object_or_404(Servicio, id=servicio_id, peluqueria=request.user.perfil.peluqueria)
    s.delete()
    messages.success(request, "Servicio eliminado.")
    return redirect('gestionar_servicios')

@login_required
def gestionar_equipo(request):
    if not hasattr(request.user, 'perfil') or not request.user.perfil.es_dueño:
        return redirect('inicio')
        
    peluqueria = request.user.perfil.peluqueria
    
    link_invitacion = request.build_absolute_uri(f"/{peluqueria.slug}/unirse-al-equipo/")
    empleados = peluqueria.empleados.all()
    
    return render(request, 'salon/panel_dueño/equipo.html', {
        'peluqueria': peluqueria, 'empleados': empleados, 'link_invitacion': link_invitacion
    })

# =======================================================
# 3. PANEL EMPLEADO (AGENDA)
# =======================================================

@login_required
def mi_agenda(request):
    try:
        empleado = request.user.empleado_perfil
    except:
        return redirect('login_custom')

    dias_semana = {0:'Lunes', 1:'Martes', 2:'Miércoles', 3:'Jueves', 4:'Viernes', 5:'Sábado', 6:'Domingo'}

    if request.method == 'POST':
        try:
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
            messages.success(request, "Horario actualizado correctamente.")
        except Exception as e:
            logger.error(f"Error actualizando horario empleado {empleado.id}: {e}")
            messages.error(request, "Hubo un error al guardar tu horario.")
            
        return redirect('mi_agenda')

    horarios = {h.dia_semana: h for h in HorarioEmpleado.objects.filter(empleado=empleado)}
    lista_dias = []
    for i, nombre in dias_semana.items():
        h = horarios.get(i)
        lista_dias.append({
            'id': i, 'nombre': nombre,
            'trabaja': h is not None,
            'inicio': h.hora_inicio.strftime('%H:%M') if h else '09:00',
            'fin': h.hora_fin.strftime('%H:%M') if h else '19:00',
            'l_ini': h.almuerzo_inicio.strftime('%H:%M') if (h and h.almuerzo_inicio) else '',
            'l_fin': h.almuerzo_fin.strftime('%H:%M') if (h and h.almuerzo_fin) else ''
        })

    # Mostrar citas futuras del empleado
    mis_citas = Cita.objects.filter(empleado=empleado, fecha_hora_inicio__gte=datetime.now()).order_by('fecha_hora_inicio')

    return render(request, 'salon/mi_horario.html', {'empleado': empleado, 'dias': lista_dias, 'mis_citas': mis_citas})

# =======================================================
# 4. PÚBLICO (RESERVAS REALES)
# =======================================================

def inicio(request):
    ciudad = request.GET.get('ciudad')
    if ciudad:
        peluquerias = Peluqueria.objects.filter(ciudad__icontains=ciudad)
    else:
        peluquerias = Peluqueria.objects.all()
        
    ciudades = Peluqueria.objects.values_list('ciudad', flat=True).distinct()
    
    return render(request, 'salon/index.html', {
        'peluquerias': peluquerias, 
        'ciudades': ciudades,
        'ciudad_actual': ciudad
    })

def landing_saas(request):
    return render(request, 'salon/landing_saas.html')

def agendar_cita(request, slug_peluqueria):
    """
    CORREGIDO: Lógica real para guardar la cita en la base de datos usando el BookingManager.
    """
    peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)
    servicios = peluqueria.servicios.all()
    empleados = peluqueria.empleados.filter(activo=True)

    if request.method == 'POST':
        try:
            # 1. Recibir datos del formulario HTML
            empleado_id = request.POST.get('empleado')
            fecha_str = request.POST.get('fecha_seleccionada') # YYYY-MM-DD
            hora_str = request.POST.get('hora_seleccionada') # HH:MM
            cliente_nombre = request.POST.get('nombre_cliente')
            cliente_telefono = request.POST.get('telefono_cliente')
            servicios_ids = request.POST.getlist('servicios') # Lista de IDs
            tipo_pago = request.POST.get('tipo_pago', 'completo')

            if not (empleado_id and fecha_str and hora_str and servicios_ids):
                raise ValueError("Faltan datos obligatorios para la reserva.")

            # 2. Preparar objetos y calcular totales
            servicios_objs = Servicio.objects.filter(id__in=servicios_ids)
            duracion_total = sum([s.duracion for s in servicios_objs], timedelta())
            precio_total = sum([s.precio for s in servicios_objs])
            
            # Fecha y Hora Inicio/Fin
            inicio_dt = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
            fin_dt = inicio_dt + duracion_total

            # 3. Lógica de Reserva ATÓMICA (Usando el BookingManager)
            def _crear_reserva_segura(empleado_bloqueado):
                # Validar superposición
                conflicto = Cita.objects.filter(
                    empleado=empleado_bloqueado,
                    estado__in=['P', 'C'],
                    fecha_hora_inicio__lt=fin_dt,
                    fecha_hora_fin__gt=inicio_dt
                ).exists()
                
                if conflicto:
                    raise ValueError("Lo sentimos, este horario acaba de ser ocupado por otra persona.")

                # Crear la cita
                nueva_cita = Cita.objects.create(
                    peluqueria=peluqueria,
                    empleado=empleado_bloqueado,
                    cliente_nombre=cliente_nombre,
                    cliente_telefono=cliente_telefono,
                    fecha_hora_inicio=inicio_dt,
                    fecha_hora_fin=fin_dt,
                    precio_total=precio_total,
                    estado='C' # Confirmada por defecto (luego integramos pago Bold)
                )
                nueva_cita.servicios.set(servicios_objs)
                return nueva_cita

            # Ejecutar con protección contra doble reserva
            cita = BookingManager.ejecutar_reserva_segura(empleado_id, _crear_reserva_segura)
            
            # 4. Enviar Notificaciones y Redirigir
            if hasattr(cita, 'enviar_notificacion_telegram'):
                try:
                    cita.enviar_notificacion_telegram()
                except Exception as e:
                    logger.warning(f"Error enviando telegram para cita {cita.id}: {e}")
            
            return redirect('confirmacion_cita', slug_peluqueria=peluqueria.slug, cita_id=cita.id)

        except Exception as e:
            logger.error(f"Error al agendar cita: {e}")
            return render(request, 'salon/agendar.html', {
                'peluqueria': peluqueria, 
                'servicios': servicios, 
                'empleados': empleados,
                'error_mensaje': f"No se pudo agendar: {str(e)}"
            })

    return render(request, 'salon/agendar.html', {'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados})

def api_obtener_horarios(request):
    """API JSON usada por el frontend de reservas para llenar el select de horas"""
    emp_id = request.GET.get('empleado_id')
    fecha_str = request.GET.get('fecha')
    servicios_ids = request.GET.get('servicios_ids') # "1,2,3"
    
    if not emp_id or not fecha_str: 
        return JsonResponse({'horas': []})

    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        emp = Empleado.objects.get(id=emp_id)
        
        # Calcular duración total de los servicios seleccionados
        duracion_total = timedelta(minutes=30) # Default
        if servicios_ids:
            # Convertimos string "1,2,3" a lista de enteros de forma segura
            ids = [int(x) for x in servicios_ids.split(',') if x.isdigit()]
            if ids:
                servicios = Servicio.objects.filter(id__in=ids)
                calc_duracion = sum([s.duracion for s in servicios], timedelta())
                if calc_duracion > timedelta(0):
                    duracion_total = calc_duracion

        horas = obtener_bloques_disponibles(emp, fecha, duracion_total)
        return JsonResponse({'horas': horas})
    except Exception as e:
        logger.error(f"Error API horarios: {e}")
        return JsonResponse({'horas': []})

def confirmacion_cita(request, slug_peluqueria, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    return render(request, 'salon/confirmacion.html', {'cita': cita})

def retorno_bold(request):
    # Lógica de retorno de pago Bold (Simplificada)
    return render(request, 'salon/confirmacion.html')
