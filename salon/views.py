from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db import transaction
from datetime import datetime, timedelta
import traceback # Para ver el error real en logs

from .models import Peluqueria, Servicio, Empleado, Cita
from .services import obtener_bloques_disponibles, verificar_conflicto_atomic

# Intentamos importar la notificación, si falla no rompemos la app
try:
    from .prueba_telegram import enviar_notificacion_telegram 
except ImportError:
    def enviar_notificacion_telegram(cita): pass

# 1. INICIO
def inicio(request):
    peluquerias = Peluqueria.objects.all()
    return render(request, 'salon/index.html', {'peluquerias': peluquerias})

# 2. API INTERNA (Para el HTML)
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

    except Exception:
        return JsonResponse({'horas': []})

# 3. AGENDAR CITA (POST WEB - DEPURADO)
def agendar_cita(request, slug_peluqueria):
    print(f"--- INICIO PROCESO AGENDAR: {slug_peluqueria} ---") # LOG 1
    peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)
    servicios = peluqueria.servicios.all()
    empleados = peluqueria.empleados.all()

    if request.method == 'POST':
        try:
            # 1. Recibir datos
            nombre = request.POST.get('nombre_cliente')
            telefono = request.POST.get('telefono_cliente')
            empleado_id = request.POST.get('empleado')
            fecha_str = request.POST.get('fecha_seleccionada')
            hora_str = request.POST.get('hora_seleccionada')
            servicios_ids = request.POST.getlist('servicios')

            print(f"Datos recibidos: {nombre}, {fecha_str}, {hora_str}, Servicios: {servicios_ids}") # LOG 2

            if not (nombre and empleado_id and fecha_str and hora_str):
                raise ValueError("Faltan datos obligatorios del formulario")

            empleado = get_object_or_404(Empleado, id=empleado_id)
            inicio_cita = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
            
            servicios_objs = Servicio.objects.filter(id__in=servicios_ids)
            if not servicios_objs:
                raise ValueError("No se seleccionaron servicios válidos")

            duracion_total = sum([s.duracion for s in servicios_objs], timedelta())
            fin_cita = inicio_cita + duracion_total
            total_precio = sum([s.precio for s in servicios_objs])

            # 2. BLINDAJE
            with transaction.atomic():
                if verificar_conflicto_atomic(empleado, inicio_cita, fin_cita):
                    print("!!! CONFLICTO DETECTADO EN ATOMIC !!!") # LOG 3
                    return render(request, 'salon/agendar.html', {
                        'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados,
                        'error_mensaje': f"⚠️ Lo sentimos, las {hora_str} ya no está disponible."
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
                print(f"✅ Cita creada ID: {cita.id}") # LOG 4
            
            # 3. Notificación
            try: enviar_notificacion_telegram(cita)
            except Exception as e: print(f"Error Telegram: {e}")
            
            # 4. REDIRECCIÓN EXPLÍCITA
            print(">>> Redirigiendo a Confirmación") # LOG 5
            return redirect('cita_confirmada')
            
        except Exception as e:
            print("❌ ERROR EN VISTA AGENDAR:")
            traceback.print_exc() # Imprime el error completo en la consola
            return render(request, 'salon/agendar.html', {
                'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados,
                'error_mensaje': f"Ocurrió un error: {str(e)}" # Mostramos el error al usuario para saber qué pasa
            })

    return render(request, 'salon/agendar.html', {
        'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados
    })

def cita_confirmada(request):
    return render(request, 'salon/confirmacion.html')