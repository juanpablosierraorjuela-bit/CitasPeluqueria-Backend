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
                # 1. Crear Usuario
                user = User.objects.create_user(username=email, email=email, password=password)
                user.first_name = nombre_contacto
                user.is_staff = True 
                user.save()

                grupo, _ = Group.objects.get_or_create(name='Dueños')
                user.groups.add(grupo)

                # 2. Crear Peluquería
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

                # 3. Vincular Perfil
                PerfilUsuario.objects.create(user=user, peluqueria=peluqueria, es_dueño=True)

                # 4. Crear Empleado (Dueño)
                empleado = Empleado.objects.create(
                    peluqueria=peluqueria,
                    nombre=nombre_contacto.split()[0],
                    apellido=nombre_contacto.split()[-1] if ' ' in nombre_contacto else '',
                    activo=True
                )

                # 5. Crear Horario por Defecto (Lun-Vie 9-6, Sab 9-2)
                for dia in range(0, 5): 
                    HorarioEmpleado.objects.create(empleado=empleado, dia_semana=dia, hora_inicio=time(9,0), hora_fin=time(18,0))
                HorarioEmpleado.objects.create(empleado=empleado, dia_semana=5, hora_inicio=time(9,0), hora_fin=time(14,0))

                # 6. Servicios de ejemplo
                Servicio.objects.create(peluqueria=peluqueria, nombre="Corte General", precio=20000, duracion=timedelta(minutes=45))

                SolicitudSaaS.objects.create(nombre_contacto=nombre_contacto, nombre_empresa=nombre_negocio, telefono=telefono, nicho="Belleza", atendido=True)

                login(request, user)
                return redirect('/admin/')
                
        except Exception as e:
            traceback.print_exc()
            return render(request, 'salon/landing_saas.html', {'error': 'Error al crear la cuenta.'})

    return render(request, 'salon/landing_saas.html')

# --- RESTO DE VISTAS (Agenda, Home, API) ---
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
    return redirect('inicio') # Simplificado, agrega tu lógica si la tienes guardada

def cita_confirmada(request):
    return render(request, 'salon/confirmacion.html')

@login_required(login_url='/admin/login/')
def dashboard_dueño(request):
    peluqueria = None
    if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
        peluqueria = request.user.perfil.peluqueria
    elif request.user.is_superuser:
        peluqueria = Peluqueria.objects.first()
    
    if not peluqueria: return HttpResponse("No tienes peluquería asignada.")
    return render(request, 'salon/dashboard.html', {'peluqueria': peluqueria})

# --- PWA: MANIFIESTO PARA INSTALAR APP ---
def manifest_view(request):
    icons = [
        {"src": "/static/img/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/static/img/icon-512.png", "sizes": "512x512", "type": "image/png"}
    ]
    return JsonResponse({
        "name": "Citas App", "short_name": "Citas", "start_url": "/", "display": "standalone",
        "background_color": "#ffffff", "theme_color": "#ec4899", "icons": icons
    })
