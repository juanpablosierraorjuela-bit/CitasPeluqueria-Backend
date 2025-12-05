import json
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages
from .models import Peluqueria, Servicio, Empleado, Cita, HorarioSemanal

def inicio(request):
    peluquerias = Peluqueria.objects.all()
    return render(request, 'salon/index.html', {'peluquerias': peluquerias})

def agendar_cita(request, slug_peluqueria):
    peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)
    servicios = Servicio.objects.filter(peluqueria=peluqueria)
    empleados = Empleado.objects.filter(peluqueria=peluqueria)

    if request.method == 'POST':
        try:
            # Recibimos una LISTA de IDs de servicios
            servicio_ids = request.POST.getlist('servicios') 
            empleado_id = request.POST.get('empleado')
            nombre = request.POST.get('nombre_cliente')
            telefono = request.POST.get('telefono_cliente')
            fecha_str = request.POST.get('fecha_seleccionada')
            hora_str = request.POST.get('hora_seleccionada')

            empleado = get_object_or_404(Empleado, id=empleado_id)
            servicios_objs = Servicio.objects.filter(id__in=servicio_ids)

            # Calcular duración total y precio total
            duracion_total = timedelta()
            precio_total = 0
            for s in servicios_objs:
                duracion_total += s.duracion
                precio_total += s.precio

            fecha_naive = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
            fecha_inicio = timezone.make_aware(fecha_naive)
            fecha_fin = fecha_inicio + duracion_total

            # Crear Cita
            cita = Cita.objects.create(
                peluqueria=peluqueria,
                empleado=empleado,
                cliente_nombre=nombre,
                cliente_telefono=telefono,
                fecha_hora_inicio=fecha_inicio,
                fecha_hora_fin=fecha_fin,
                precio_total=precio_total
            )
            # Asignar relación muchos a muchos
            cita.servicios.set(servicios_objs)
            
            return redirect('cita_confirmada')
            
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, 'salon/agendar.html', {'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados})

# --- API MEJORADA PARA MÚLTIPLES SERVICIOS ---
def obtener_horas_disponibles(request):
    empleado_id = request.GET.get('empleado_id')
    fecha_str = request.GET.get('fecha')
    # Recibimos string de IDs separados por coma "1,2,3"
    servicios_ids_str = request.GET.get('servicios_ids', '') 

    if not (empleado_id and fecha_str and servicios_ids_str):
        return JsonResponse({'error': 'Faltan datos'}, status=400)

    try:
        empleado = Empleado.objects.get(id=empleado_id)
        peluqueria = empleado.peluqueria
        
        # Calcular duración total de TODOS los servicios seleccionados
        ids_list = servicios_ids_str.split(',')
        servicios_objs = Servicio.objects.filter(id__in=ids_list)
        duracion_total = sum([s.duracion for s in servicios_objs], timedelta())

        fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        dia_semana = fecha_obj.weekday()

        try:
            horario = HorarioSemanal.objects.get(empleado=empleado, dia_semana=dia_semana)
        except HorarioSemanal.DoesNotExist:
            return JsonResponse({'horas': [], 'mensaje': 'El estilista descansa este día.'})

        inicio_jornada = max(peluqueria.hora_apertura, horario.hora_inicio)
        fin_jornada = min(peluqueria.hora_cierre, horario.hora_fin)

        citas_existentes = Cita.objects.filter(
            empleado=empleado,
            fecha_hora_inicio__date=fecha_obj,
            estado__in=['P', 'C']
        )

        slots = []
        tiempo_actual = datetime.combine(fecha_obj, inicio_jornada)
        limite = datetime.combine(fecha_obj, fin_jornada)

        while tiempo_actual + duracion_total <= limite:
            inicio_slot = tiempo_actual
            fin_slot = tiempo_actual + duracion_total
            
            # Verificar almuerzo
            en_almuerzo = False
            if horario.descanso_inicio and horario.descanso_fin:
                ini_desc = datetime.combine(fecha_obj, horario.descanso_inicio)
                fin_desc = datetime.combine(fecha_obj, horario.descanso_fin)
                if (inicio_slot < fin_desc and fin_slot > ini_desc): en_almuerzo = True

            # Verificar citas
            choca = False
            if not en_almuerzo:
                ini_aware = timezone.make_aware(inicio_slot)
                fin_aware = timezone.make_aware(fin_slot)
                for c in citas_existentes:
                    if (ini_aware < c.fecha_hora_fin) and (fin_aware > c.fecha_hora_inicio):
                        choca = True; break
            
            if not choca and not en_almuerzo:
                slots.append(inicio_slot.strftime("%H:%M"))

            tiempo_actual += timedelta(minutes=30)

        return JsonResponse({'horas': slots})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def cita_confirmada(request):
    return render(request, 'salon/confirmacion.html')