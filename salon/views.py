from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db import transaction
from django.utils.timezone import make_aware # IMPORTANTE
from datetime import datetime, timedelta
import traceback

from .models import Peluqueria, Servicio, Empleado, Cita
from .services import obtener_bloques_disponibles, verificar_conflicto_atomic

def inicio(request):
    peluquerias = Peluqueria.objects.all()
    return render(request, 'salon/index.html', {'peluquerias': peluquerias})

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
            
            # --- CORRECCIÓN DE ZONA HORARIA ---
            fecha_naive = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
            try:
                inicio_cita = make_aware(fecha_naive) # La convertimos a 'consciente'
            except ValueError:
                inicio_cita = fecha_naive # Si ya lo era, lo dejamos así

            servicios_objs = Servicio.objects.filter(id__in=servicios_ids)
            duracion_total = sum([s.duracion for s in servicios_objs], timedelta())
            fin_cita = inicio_cita + duracion_total
            total_precio = sum([s.precio for s in servicios_objs])

            # BLINDAJE
            with transaction.atomic():
                # Ahora verificamos con fechas AWARE, por lo que no debería fallar
                if verificar_conflicto_atomic(empleado, inicio_cita, fin_cita):
                    print("CONFLICTO: Horario ocupado")
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
            
            # Telegram es automático gracias a models.py
            print("EXITO: Redirigiendo...")
            return redirect('cita_confirmada')
            
        except Exception as e:
            traceback.print_exc() # Ver error en consola
            return render(request, 'salon/agendar.html', {
                'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados,
                'error_mensaje': f"Ocurrió un error técnico: {str(e)}"
            })

    return render(request, 'salon/agendar.html', {
        'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados
    })

def cita_confirmada(request):
    return render(request, 'salon/confirmacion.html')