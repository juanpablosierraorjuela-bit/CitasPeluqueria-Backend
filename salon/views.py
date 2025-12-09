from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.db.models import Sum
from django.contrib.auth import login
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import make_aware, now
from django.utils.text import slugify
from datetime import datetime, timedelta, time
import hashlib
import traceback
import requests

from .models import Peluqueria, Servicio, Empleado, Cita, PerfilUsuario, SolicitudSaaS, HorarioEmpleado
from .services import obtener_bloques_disponibles, verificar_conflicto_atomic
from . import api  # Importamos api para las rutas

# --- VISTA PARA EL REGISTRO DE NUEVOS SALONES (SAAS) ---
def landing_saas(request):
    if request.method == 'POST':
        try:
            nombre_negocio = request.POST.get('empresa')
            nombre_contacto = request.POST.get('nombre')
            telefono = request.POST.get('telefono')
            email = request.POST.get('email')
            password = request.POST.get('password')
            
            if User.objects.filter(username=email).exists():
                return render(request, 'salon/landing_saas.html', {'error': 'Este correo ya está registrado.'})

            with transaction.atomic():
                user = User.objects.create_user(username=email, email=email, password=password)
                user.first_name = nombre_contacto
                user.is_staff = True 
                user.save()

                grupo, _ = Group.objects.get_or_create(name='Dueños')
                user.groups.add(grupo)

                base_slug = slugify(nombre_negocio)
                slug = base_slug
                counter = 1
                while Peluqueria.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                
                peluqueria = Peluqueria.objects.create(
                    nombre=nombre_negocio,
                    nombre_visible=nombre_negocio,
                    slug=slug,
                    telefono=telefono
                )

                PerfilUsuario.objects.create(user=user, peluqueria=peluqueria, es_dueño=True)

                # Creamos también el perfil de empleado para que el dueño pueda agendarse
                empleado = Empleado.objects.create(
                    peluqueria=peluqueria,
                    user=user,
                    nombre=nombre_contacto.split()[0],
                    apellido=nombre_contacto.split()[-1] if ' ' in nombre_contacto else '',
                    activo=True
                )

                # Horario por defecto
                for dia in range(0, 5): 
                    HorarioEmpleado.objects.create(empleado=empleado, dia_semana=dia, hora_inicio=time(9,0), hora_fin=time(18,0), almuerzo_inicio=time(13,0), almuerzo_fin=time(14,0))
                HorarioEmpleado.objects.create(empleado=empleado, dia_semana=5, hora_inicio=time(9,0), hora_fin=time(14,0))

                Servicio.objects.create(peluqueria=peluqueria, nombre="Corte General", precio=20000, duracion=timedelta(minutes=45))

                SolicitudSaaS.objects.create(nombre_contacto=nombre_contacto, nombre_empresa=nombre_negocio, telefono=telefono, nicho="Belleza", atendido=True)

                login(request, user)
                return redirect('/admin/')
                
        except Exception as e:
            traceback.print_exc()
            return render(request, 'salon/landing_saas.html', {'error': 'Error al crear la cuenta.'})

    return render(request, 'salon/landing_saas.html')

# --- VISTAS WEB PÚBLICAS ---
def inicio(request):
    ciudad = request.GET.get('ciudad')
    ciudades = Peluqueria.objects.values_list('ciudad', flat=True).distinct().order_by('ciudad')
    peluquerias = Peluqueria.objects.all()
    if ciudad and ciudad != 'Todas': peluquerias = peluquerias.filter(ciudad__iexact=ciudad)
    return render(request, 'salon/index.html', {'peluquerias': peluquerias, 'ciudades': ciudades, 'ciudad_actual': ciudad})

def obtener_horas_disponibles(request):
    try:
        emp_id = request.GET.get('empleado_id')
        fecha = request.GET.get('fecha')
        s_ids = request.GET.get('servicios_ids', '').split(',')
        
        if not (emp_id and fecha and s_ids): return JsonResponse({'horas': []})
        
        fecha_dt = datetime.strptime(fecha, "%Y-%m-%d").date()
        empleado = get_object_or_404(Empleado, id=emp_id)
        
        duracion = timedelta()
        for sid in s_ids:
            if sid: 
                try: duracion += Servicio.objects.get(id=sid).duracion
                except: pass
            
        horas = obtener_bloques_disponibles(empleado, fecha_dt, duracion)
        return JsonResponse({'horas': horas})
    except: return JsonResponse({'horas': []})

def agendar_cita(request, slug_peluqueria):
    peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)
    servicios = peluqueria.servicios.all()
    empleados = peluqueria.empleados.all()

    if request.method == 'POST':
        try:
            nombre = request.POST.get('nombre_cliente')
            telefono = request.POST.get('telefono_cliente')
            empleado_id = request.POST.get('empleado')
            fecha_str = request.POST.get('fecha_seleccionada')
            hora_str = request.POST.get('hora_seleccionada')
            servicios_ids = request.POST.getlist('servicios')
            tipo_pago = request.POST.get('tipo_pago', 'completo') 

            if not (nombre and empleado_id and fecha_str and hora_str): raise ValueError("Faltan datos")

            empleado = get_object_or_404(Empleado, id=empleado_id)
            fecha_naive = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
            try: inicio_cita = make_aware(fecha_naive) 
            except ValueError: inicio_cita = fecha_naive

            servicios_objs = Servicio.objects.filter(id__in=servicios_ids)
            duracion_total = sum([s.duracion for s in servicios_objs], timedelta())
            fin_cita = inicio_cita + duracion_total
            total_precio = sum([s.precio for s in servicios_objs])

            usa_bold = bool(peluqueria.bold_api_key and peluqueria.bold_integrity_key)
            estado_inicial = 'P' if usa_bold else 'C'

            with transaction.atomic():
                if verificar_conflicto_atomic(empleado, inicio_cita, fin_cita):
                    return render(request, 'salon/agendar.html', {'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados, 'error_mensaje': "⚠️ Horario ya reservado por otra persona."})
                
                cita = Cita.objects.create(
                    peluqueria=peluqueria, cliente_nombre=nombre, cliente_telefono=telefono,
                    empleado=empleado, fecha_hora_inicio=inicio_cita, fecha_hora_fin=fin_cita,
                    precio_total=total_precio, estado=estado_inicial
                )
                cita.servicios.set(servicios_objs)

            if usa_bold:
                porcentaje = peluqueria.porcentaje_abono if peluqueria.porcentaje_abono > 0 else 50
                monto = int(total_precio * porcentaje / 100) if tipo_pago == 'abono' else int(total_precio)
                cita.abono_pagado = monto
                ref = f"CITA-{cita.id}-{int(datetime.now().timestamp())}"
                cita.referencia_pago_bold = ref
                cita.save()
                firma = hashlib.sha256(f"{ref}{monto}COP{peluqueria.bold_integrity_key}".encode('utf-8')).hexdigest()
                return render(request, 'salon/pago_bold.html', {'cita': cita, 'monto_anticipo': monto, 'signature': firma, 'peluqueria': peluqueria, 'referencia': ref})
            else:
                cita.enviar_notificacion_telegram()
                return redirect('cita_confirmada')
            
        except Exception:
            traceback.print_exc()
            return render(request, 'salon/agendar.html', {'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados, 'error_mensaje': "Error técnico."})

    return render(request, 'salon/agendar.html', {'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados})

@csrf_exempt 
def retorno_bold(request):
    return redirect('inicio')

def cita_confirmada(request):
    return render(request, 'salon/confirmacion.html')

# --- DASHBOARD DUEÑO ---
@login_required(login_url='/admin/login/')
def dashboard_dueño(request):
    # CORRECCIÓN: Solo redirigir si es empleado Y NO ES DUEÑO
    es_dueno = hasattr(request.user, 'perfil') and request.user.perfil.es_dueño
    if hasattr(request.user, 'empleado_perfil') and not es_dueno:
        return redirect('mi_horario')

    peluqueria = None
    if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
        peluqueria = request.user.perfil.peluqueria
    elif request.user.is_superuser:
        peluqueria = Peluqueria.objects.first()
    
    if not peluqueria: return HttpResponse("No tienes peluquería asignada.")
    
    hoy = now().date()
    citas_hoy = Cita.objects.filter(peluqueria=peluqueria, fecha_hora_inicio__date=hoy).count()
    ingresos = Cita.objects.filter(peluqueria=peluqueria, fecha_hora_inicio__month=hoy.month).aggregate(Sum('precio_total'))['precio_total__sum'] or 0
    proximas = Cita.objects.filter(peluqueria=peluqueria, fecha_hora_inicio__gte=now()).order_by('fecha_hora_inicio')[:5]

    return render(request, 'salon/dashboard.html', {
        'peluqueria': peluqueria,
        'citas_hoy': citas_hoy,
        'ingresos_mes': ingresos,
        'proximas_citas': proximas
    })

# --- GESTIÓN DE EQUIPO ---
@login_required
def crear_empleado_con_usuario(request):
    if not hasattr(request.user, 'perfil') or not request.user.perfil.es_dueño:
        return redirect('inicio')
    
    peluqueria = request.user.perfil.peluqueria

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        if User.objects.filter(username=email).exists():
            return render(request, 'salon/crear_empleado.html', {'error': 'El correo ya existe'})

        try:
            with transaction.atomic():
                user_emp = User.objects.create_user(username=email, email=email, password=password)
                user_emp.first_name = nombre
                user_emp.save()
                
                grupo_emp, _ = Group.objects.get_or_create(name='Empleados')
                user_emp.groups.add(grupo_emp)

                PerfilUsuario.objects.create(user=user_emp, peluqueria=peluqueria, es_dueño=False)

                empleado = Empleado.objects.create(
                    peluqueria=peluqueria,
                    user=user_emp,
                    nombre=nombre,
                    apellido="",
                    email_contacto=email
                )
                
                for dia in range(0, 5):
                    HorarioEmpleado.objects.create(
                        empleado=empleado, dia_semana=dia, 
                        hora_inicio=time(9,0), hora_fin=time(18,0),
                        almuerzo_inicio=time(13,0), almuerzo_fin=time(14,0)
                    )
            return redirect('dashboard_dueño')
        except Exception as e:
            return render(request, 'salon/crear_empleado.html', {'error': f'Error: {str(e)}'})

    return render(request, 'salon/crear_empleado.html')

# --- MI HORARIO (GUARDADO MASIVO) ---
@login_required
def mi_horario_empleado(request):
    try:
        empleado = request.user.empleado_perfil 
    except:
        return HttpResponse("No tienes un perfil de estilista asignado.")

    dias_semana = {0:'Lunes', 1:'Martes', 2:'Miércoles', 3:'Jueves', 4:'Viernes', 5:'Sábado', 6:'Domingo'}

    if request.method == 'POST':
        # 1. Obtener listas de datos
        ids_dias = request.POST.getlist('dia_id') # [0, 1, 2...]
        inicios = request.POST.getlist('hora_inicio')
        fines = request.POST.getlist('hora_fin')
        lunch_inis = request.POST.getlist('almuerzo_inicio')
        lunch_fins = request.POST.getlist('almuerzo_fin')
        
        # Checkboxes: devuelve una lista solo con los IDs marcados (ej: ['0', '1', '4'])
        dias_activos = request.POST.getlist('dias_activos') 

        with transaction.atomic():
            # Limpiamos todo el horario anterior para evitar conflictos
            HorarioEmpleado.objects.filter(empleado=empleado).delete()

            # Recorremos los datos enviados (asumiendo que siempre llegan 7 días en orden)
            for i, dia_str in enumerate(ids_dias):
                dia_id = int(dia_str)
                
                # Verificamos si este día fue marcado en los checkbox
                if dia_str in dias_activos:
                    # Guardamos el nuevo horario
                    HorarioEmpleado.objects.create(
                        empleado=empleado,
                        dia_semana=dia_id,
                        hora_inicio=inicios[i],
                        hora_fin=fines[i],
                        almuerzo_inicio=lunch_inis[i] if lunch_inis[i] else None,
                        almuerzo_fin=lunch_fins[i] if lunch_fins[i] else None
                    )

        # Redirigimos a la misma página para ver cambios
        return redirect('mi_horario')

    # --- GET: Preparar datos para mostrar ---
    horarios_db = HorarioEmpleado.objects.filter(empleado=empleado)
    horario_dict = {h.dia_semana: h for h in horarios_db}
    
    lista_dias = []
    for i, nombre in dias_semana.items():
        obj = horario_dict.get(i)
        lista_dias.append({
            'id': i, 
            'nombre': nombre,
            'trabaja': obj is not None,
            'inicio': obj.hora_inicio.strftime('%H:%M') if obj else '09:00',
            'fin': obj.hora_fin.strftime('%H:%M') if obj else '18:00',
            'l_ini': obj.almuerzo_inicio.strftime('%H:%M') if (obj and obj.almuerzo_inicio) else '',
            'l_fin': obj.almuerzo_fin.strftime('%H:%M') if (obj and obj.almuerzo_fin) else '',
        })

    return render(request, 'salon/mi_horario.html', {'dias': lista_dias, 'empleado': empleado})

def manifest_view(request):
    icons = [
        {"src": "/static/img/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/static/img/icon-512.png", "sizes": "512x512", "type": "image/png"}
    ]
    return JsonResponse({
        "name": "Citas App", "short_name": "Citas", "start_url": "/", "display": "standalone",
        "background_color": "#ffffff", "theme_color": "#ec4899", "icons": icons
    })
