# UBICACIÓN: salon/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from datetime import timedelta, time, datetime
import hashlib

from .models import Peluqueria, Servicio, Empleado, Cita, PerfilUsuario, HorarioEmpleado
from .forms import ConfigNegocioForm, ServicioForm, NuevoEmpleadoForm
from .services import obtener_bloques_disponibles, verificar_conflicto_atomic
from salon.utils.booking_lock import BookingManager

# =======================================================
# 1. AUTENTICACIÓN CENTRALIZADA
# =======================================================

def login_view(request):
    if request.user.is_authenticated:
        return redirigir_usuario(request.user)

    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(request, username=u, password=p)
        
        if user is not None:
            login(request, user)
            return redirigir_usuario(user)
        else:
            return render(request, 'salon/login.html', {'error': 'Usuario o contraseña incorrectos'})
            
    return render(request, 'salon/login.html')

def redirigir_usuario(user):
    """El semáforo que dice a dónde va cada quién"""
    if user.is_superuser:
        return redirect('/admin/') # Tú vas al Django Admin
    
    # Verificamos perfil
    try:
        perfil = user.perfil
        if perfil.es_dueño:
            return redirect('panel_negocio') # Dueño -> Panel HTML
        elif hasattr(user, 'empleado_perfil'):
            return redirect('mi_agenda') # Empleado -> Agenda HTML
    except:
        pass
        
    return redirect('inicio')

def logout_view(request):
    logout(request)
    return redirect('login_usuario')

# =======================================================
# 2. PANEL DEL DUEÑO (HTML INDEPENDIENTE)
# =======================================================

@login_required
def panel_negocio(request):
    # SEGURIDAD: Solo dueños
    if not hasattr(request.user, 'perfil') or not request.user.perfil.es_dueño:
        return redirect('inicio')
    
    peluqueria = request.user.perfil.peluqueria
    
    # KPIs Rápidos
    citas_hoy = peluqueria.citas.filter(fecha_hora_inicio__date=datetime.now().date()).count()
    empleados = peluqueria.empleados.filter(activo=True)
    servicios = peluqueria.servicios.all()

    return render(request, 'salon/panel_dueño/inicio.html', {
        'peluqueria': peluqueria,
        'citas_hoy': citas_hoy,
        'empleados': empleados,
        'servicios': servicios
    })

@login_required
def configuracion_negocio(request):
    if not request.user.perfil.es_dueño: return redirect('inicio')
    peluqueria = request.user.perfil.peluqueria

    if request.method == 'POST':
        form = ConfigNegocioForm(request.POST, instance=peluqueria)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuración actualizada correctamente.')
            return redirect('panel_negocio')
    else:
        form = ConfigNegocioForm(instance=peluqueria)

    return render(request, 'salon/panel_dueño/configuracion.html', {'form': form, 'peluqueria': peluqueria})

@login_required
def gestionar_servicios(request):
    if not request.user.perfil.es_dueño: return redirect('inicio')
    peluqueria = request.user.perfil.peluqueria
    
    if request.method == 'POST':
        # Agregar nuevo servicio
        form = ServicioForm(request.POST)
        if form.is_valid():
            nuevo_serv = form.save(commit=False)
            nuevo_serv.peluqueria = peluqueria
            nuevo_serv.duracion = timedelta(minutes=form.cleaned_data['duracion_minutos'])
            nuevo_serv.save()
            messages.success(request, "Servicio agregado.")
            return redirect('gestionar_servicios')
    else:
        form = ServicioForm()

    servicios = peluqueria.servicios.all()
    return render(request, 'salon/panel_dueño/servicios.html', {'servicios': servicios, 'form': form})

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
    
    if request.method == 'POST':
        form = NuevoEmpleadoForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            if User.objects.filter(username=data['email']).exists():
                messages.error(request, "Ese correo ya está en uso.")
            else:
                with transaction.atomic():
                    # 1. Crear Usuario
                    user = User.objects.create_user(username=data['email'], email=data['email'], password=data['password'])
                    user.first_name = data['nombre']
                    user.save()
                    
                    # 2. Perfil (No es dueño)
                    PerfilUsuario.objects.create(user=user, peluqueria=peluqueria, es_dueño=False)
                    
                    # 3. Empleado
                    emp = Empleado.objects.create(
                        peluqueria=peluqueria, user=user, 
                        nombre=data['nombre'], apellido=data['apellido'], 
                        email_contacto=data['email']
                    )
                    
                    # 4. Horarios Default
                    for i in range(7):
                        HorarioEmpleado.objects.create(
                            empleado=emp, dia_semana=i, 
                            hora_inicio=time(9,0), hora_fin=time(18,0)
                        )
                
                messages.success(request, f"Empleado {data['nombre']} creado.")
                return redirect('gestionar_equipo')
    else:
        form = NuevoEmpleadoForm()

    empleados = peluqueria.empleados.all()
    return render(request, 'salon/panel_dueño/equipo.html', {'empleados': empleados, 'form': form})

# =======================================================
# 3. PANEL DEL EMPLEADO (AGENDA)
# =======================================================

@login_required
def mi_agenda(request):
    try:
        empleado = request.user.empleado_perfil
    except:
        return redirect('panel_negocio') # Si entra un dueño aquí, lo mandamos a su panel

    dias_semana = {0:'Lunes', 1:'Martes', 2:'Miércoles', 3:'Jueves', 4:'Viernes', 5:'Sábado', 6:'Domingo'}

    if request.method == 'POST':
        # Guardar Horarios
        HorarioEmpleado.objects.filter(empleado=empleado).delete()
        for i in range(7):
            if request.POST.get(f'trabaja_{i}'):
                HorarioEmpleado.objects.create(
                    empleado=empleado, dia_semana=i,
                    hora_inicio=request.POST.get(f'inicio_{i}'),
                    hora_fin=request.POST.get(f'fin_{i}'),
                    almuerzo_inicio=request.POST.get(f'lunch_ini_{i}') or None,
                    almuerzo_fin=request.POST.get(f'lunch_fin_{i}') or None
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
            'fin': h.hora_fin.strftime('%H:%M') if h else '18:00',
            'l_ini': h.almuerzo_inicio.strftime('%H:%M') if (h and h.almuerzo_inicio) else '',
            'l_fin': h.almuerzo_fin.strftime('%H:%M') if (h and h.almuerzo_fin) else ''
        })

    # Citas Futuras
    citas = Cita.objects.filter(empleado=empleado, fecha_hora_inicio__gte=datetime.now()).order_by('fecha_hora_inicio')

    return render(request, 'salon/panel_empleado/agenda.html', {
        'dias': lista_dias, 
        'empleado': empleado,
        'citas': citas
    })

# =======================================================
# 4. PUBLICAS (CLIENTE FINAL) - Mantengo las esenciales
# =======================================================

def inicio(request):
    # ... (Tu código existente de inicio)
    peluquerias = Peluqueria.objects.all()
    return render(request, 'salon/index.html', {'peluquerias': peluquerias})

def agendar_cita(request, slug_peluqueria):
    # ... (Tu código existente de agendar, asegúrate de importar BookingManager y services)
    # NOTA: Mantén la lógica que ya tenías, funciona bien.
    return render(request, 'salon/agendar.html', {'peluqueria': get_object_or_404(Peluqueria, slug=slug_peluqueria)})
