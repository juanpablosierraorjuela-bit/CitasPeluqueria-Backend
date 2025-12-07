from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Sum, Count
from django.utils.timezone import make_aware, now
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta
import traceback

from .models import Peluqueria, Servicio, Empleado, Cita
from .services import obtener_bloques_disponibles, verificar_conflicto_atomic

# 1. VISTA DE INICIO
def inicio(request):
    peluquerias = Peluqueria.objects.all()
    return render(request, 'salon/index.html', {'peluquerias': peluquerias})

# 2. API PARA CALCULAR HORARIOS DISPONIBLES
def obtener_horas_disponibles(request):
    try:
        empleado_id = request.GET.get('empleado_id')
        fecha_str = request.GET.get('fecha')
        servicios_ids = request.GET.get('servicios_ids', '').split(',')

        if not (empleado_id and fecha_str and servicios_ids):
            return JsonResponse({'horas': []})

        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        empleado = get_object_or_404(Empleado, id=empleado_id)
        
        duracion_total = timedelta(minutes=0)
        for sid in servicios_ids:
            if sid:
                try:
                    s = Servicio.objects.get(id=sid)
                    duracion_total += s.duracion
                except: pass
        
        horas = obtener_bloques_disponibles(empleado, fecha, duracion_total)
        return JsonResponse({'horas': horas})

    except Exception as e:
        print(f"Error API Horarios: {e}")
        return JsonResponse({'horas': []})

# 3. AGENDAR CITA
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

            print(f"INTENTO AGENDAR: {nombre} | {fecha_str} {hora_str}")

            if not (nombre and empleado_id and fecha_str and hora_str):
                raise ValueError("Faltan datos obligatorios (fecha u hora vacía)")

            empleado = get_object_or_404(Empleado, id=empleado_id)
            
            fecha_naive = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
            try:
                inicio_cita = make_aware(fecha_naive) 
            except ValueError:
                inicio_cita = fecha_naive

            servicios_objs = Servicio.objects.filter(id__in=servicios_ids)
            duracion_total = sum([s.duracion for s in servicios_objs], timedelta())
            fin_cita = inicio_cita + duracion_total
            total_precio = sum([s.precio for s in servicios_objs])

            with transaction.atomic():
                if verificar_conflicto_atomic(empleado, inicio_cita, fin_cita):
                    print("CONFLICTO: Horario ocupado o Ausencia")
                    return render(request, 'salon/agendar.html', {
                        'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados,
                        'error_mensaje': f"⚠️ Lo sentimos, las {hora_str} ya no está disponible (ocupado o día libre)."
                    })
                
                cita = Cita.objects.create(
                    peluqueria=peluqueria,
                    cliente_nombre=nombre,
                    cliente_telefono=telefono,
                    empleado=empleado,
                    fecha_hora_inicio=inicio_cita,
                    fecha_hora_fin=fin_cita,
                    precio_total=total_precio,
                    estado='C'
                )
                cita.servicios.set(servicios_objs)
            
            print("EXITO: Redirigiendo...")
            return redirect('cita_confirmada')
            
        except Exception as e:
            traceback.print_exc() 
            return render(request, 'salon/agendar.html', {
                'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados,
                'error_mensaje': f"Ocurrió un error técnico: {str(e)}"
            })

    return render(request, 'salon/agendar.html', {
        'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados
    })

def cita_confirmada(request):
    return render(request, 'salon/confirmacion.html')

# --- 4. NUEVA VISTA DE DASHBOARD ---
@login_required(login_url='/admin/login/')
def dashboard_dueño(request):
    # Intentar obtener la peluquería del usuario logueado
    try:
        # Asumiendo que usas PerfilUsuario vinculado al User
        peluqueria = request.user.perfil.peluqueria
    except:
        peluqueria = None

    if not peluqueria:
        # Si es superusuario sin peluquería, mostramos la primera para demo
        if request.user.is_superuser:
            peluqueria = Peluqueria.objects.first()
        
        if not peluqueria:
             return render(request, 'salon/error_dashboard.html', {'mensaje': 'No tienes una peluquería asignada.'})

    # Estadísticas
    hoy = now().date()
    mes_actual = hoy.month
    
    # Citas de hoy
    citas_hoy = Cita.objects.filter(peluqueria=peluqueria, fecha_hora_inicio__date=hoy).count()
    
    # Ingresos del mes
    ingresos_mes = Cita.objects.filter(
        peluqueria=peluqueria, 
        fecha_hora_inicio__month=mes_actual, 
        estado='C'
    ).aggregate(Sum('precio_total'))['precio_total__sum'] or 0

    # Próximas 5 citas
    proximas_citas = Cita.objects.filter(
        peluqueria=peluqueria, 
        fecha_hora_inicio__gte=now(),
        estado='C'
    ).order_by('fecha_hora_inicio')[:5]

    context = {
        'peluqueria': peluqueria,
        'citas_hoy': citas_hoy,
        'ingresos_mes': ingresos_mes,
        'proximas_citas': proximas_citas,
    }
    return render(request, 'salon/dashboard.html', context)

# ... (MANTÉN TODO EL CÓDIGO ANTERIOR IGUAL) ...

# AL FINAL DEL ARCHIVO AGREGA ESTO:

def manifest_view(request):
    """
    Devuelve el archivo manifest.json para que el celular reconozca la web como App.
    """
    manifest_data = {
        "name": "Citas Peluquería",
        "short_name": "Mi Salón",
        "start_url": "/",
        "display": "standalone", # Pantalla completa (sin barra de navegador)
        "background_color": "#ffffff",
        "theme_color": "#ec4899", # Color rosado de tu marca
        "orientation": "portrait",
        "icons": [
            {
                # Usaremos un icono genérico de CDN por ahora. 
                # IDEAL: Sube tu propio logo a static/img/icon-192.png
                "src": "https://cdn-icons-png.flaticon.com/512/3899/3899618.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "https://cdn-icons-png.flaticon.com/512/3899/3899618.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }
    return JsonResponse(manifest_data)