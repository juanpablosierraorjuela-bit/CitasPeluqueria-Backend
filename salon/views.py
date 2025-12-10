# UBICACIÓN: salon/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.http import JsonResponse
from django.contrib import messages
from datetime import timedelta, time, datetime
import hashlib
import json

# Importaciones locales
from .models import Peluqueria, Servicio, Empleado, Cita, PerfilUsuario, HorarioEmpleado, SolicitudSaaS
from .forms import ConfigNegocioForm, ServicioForm, NuevoEmpleadoForm, RegistroPublicoEmpleadoForm
from .services import obtener_bloques_disponibles, verificar_conflicto_atomic
from salon.utils.booking_lock import BookingManager

# =======================================================
# 1. AUTENTICACIÓN Y REGISTRO
# =======================================================

def login_custom(request):
    """Login centralizado que redirige según el rol"""
    if request.user.is_authenticated:
        return redirigir_segun_rol(request.user)

    if request.method == 'POST':
        u = request.POST.get('email') # Usamos el email como username
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
                print(e)
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
    citas_hoy = peluqueria.citas.filter(fecha_hora_inicio__date=datetime.now().date()).count()
    empleados = peluqueria.empleados.filter(activo=True)
    servicios = peluqueria.servicios.all()

    return render(request, 'salon/panel_dueño/inicio.html', {
        'peluqueria': peluqueria, 'citas_hoy': citas_hoy, 'empleados': empleados, 'servicios': servicios
    })

@login_required
def configuracion_negocio(request):
    if not request.user.perfil.es_dueño: return redirect('inicio')
    peluqueria = request.user.perfil.peluqueria

    if request.method == 'POST':
        form = ConfigNegocioForm(request.POST, instance=peluqueria)
        if form.is_valid():
            form.save()
            messages.success(request, 'Guardado correctamente.')
            return redirect('panel_negocio')
    else:
        form = ConfigNegocioForm(instance=peluqueria)
    
    # Reutilizamos la plantilla de crear empleado o una simple para config, 
    # asumiendo que crearás 'configuracion.html' similar a 'crear_empleado.html'
    return render(request, 'salon/crear_empleado.html', {'form': form, 'titulo': 'Configuración del Negocio'}) 

@login_required
def gestionar_servicios(request):
    if not request.user.perfil.es_dueño: return redirect('inicio')
    peluqueria = request.user.perfil.peluqueria
    
    if request.method == 'POST':
        form = ServicioForm(request.POST)
        if form.is_valid():
            nuevo = form.save(commit=False)
            nuevo.peluqueria = peluqueria
            nuevo.duracion = timedelta(minutes=form.cleaned_data['duracion_minutos'])
            nuevo.save()
            return redirect('gestionar_servicios')
    else:
        form = ServicioForm()

    servicios = peluqueria.servicios.all()
    # Usamos una plantilla simple o reutilizamos dashboard pasando contexto
    return render(request, 'salon/dashboard.html', {'custom_content': 'servicios', 'servicios': servicios, 'form': form, 'peluqueria': peluqueria})

@login_required
def eliminar_servicio(request, servicio_id):
    if not request.user.perfil.es_dueño: return redirect('inicio')
    s = get_object_or_404(Servicio, id=servicio_id, peluqueria=request.user.perfil.peluqueria)
    s.delete()
    return redirect('gestionar_servicios')

@login_required
def gestionar_equipo(request):
    if not request.user.perfil.es_dueño: return redirect('inicio')
    peluqueria = request.user.perfil.peluqueria
    
    # Aquí mostramos el link de invitación
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
        messages.success(request, "Horario actualizado")
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

    return render(request, 'salon/mi_horario.html', {'empleado': empleado, 'dias': lista_dias})

# =======================================================
# 4. PÚBLICO (RESERVAS)
# =======================================================

def inicio(request):
    peluquerias = Peluqueria.objects.all()
    return render(request, 'salon/index.html', {'peluquerias': peluquerias})

def landing_saas(request):
    if request.method == 'POST':
        # Aquí crearías la peluquería nueva si implementas registro automático de dueños
        pass
    return render(request, 'salon/landing_saas.html')

def agendar_cita(request, slug_peluqueria):
    peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)
    servicios = peluqueria.servicios.all()
    empleados = peluqueria.empleados.filter(activo=True)

    if request.method == 'POST':
        try:
            empleado_id = request.POST.get('empleado')
            fecha_str = request.POST.get('fecha_seleccionada') # YYYY-MM-DD
            hora_str = request.POST.get('hora_seleccionada') # HH:MM
            cliente_nombre = request.POST.get('nombre_cliente')
            cliente_telefono = request.POST.get('telefono_cliente')
            servicios_ids = request.POST.getlist('servicios') # Debe venir del frontend como lista

            # ... Lógica de creación de cita (simplificada para este ejemplo) ...
            # Aquí deberías llamar a tu BookingManager o lógica de creación
            # Por ahora redirigimos a Bold si hay key
            
            return redirect('inicio') # Placeholder
        except Exception as e:
            return render(request, 'salon/agendar.html', {'peluqueria': peluqueria, 'error_mensaje': str(e)})

    return render(request, 'salon/agendar.html', {'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados})

def api_obtener_horarios(request):
    """API JSON usada por el frontend de reservas para llenar el select de horas"""
    emp_id = request.GET.get('empleado_id')
    fecha_str = request.GET.get('fecha')
    
    if not emp_id or not fecha_str: return JsonResponse({'horas': []})

    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        emp = Empleado.objects.get(id=emp_id)
        # Asumimos duración de 30 min por defecto o sumamos servicios
        horas = obtener_bloques_disponibles(emp, fecha, timedelta(minutes=30))
        return JsonResponse({'horas': horas})
    except:
        return JsonResponse({'horas': []})

def confirmacion_cita(request, slug_peluqueria, cita_id):
    return render(request, 'salon/confirmacion.html')

def retorno_bold(request):
    return render(request, 'salon/confirmacion.html')
