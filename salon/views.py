import json
from datetime import datetime, timedelta, time
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages
from .models import Peluqueria, Servicio, Empleado, Cita, HorarioSemanal

# --- VISTA PRINCIPAL (HTML) ---
def inicio(request):
    peluquerias = Peluqueria.objects.all()
    return render(request, 'salon/index.html', {'peluquerias': peluquerias})

def agendar_cita(request, slug_peluqueria):
    peluqueria_actual = get_object_or_404(Peluqueria, slug=slug_peluqueria)
    servicios = Servicio.objects.filter(peluqueria=peluqueria_actual)
    empleados = Empleado.objects.filter(peluqueria=peluqueria_actual)

    if request.method == 'POST':
        # Guardado de cita
        try:
            servicio_id = request.POST.get('servicio')
            empleado_id = request.POST.get('empleado')
            nombre = request.POST.get('nombre_cliente')
            telefono = request.POST.get('telefono_cliente')
            fecha_str = request.POST.get('fecha_seleccionada') # Llega como "2025-12-20"
            hora_str = request.POST.get('hora_seleccionada')   # Llega como "14:30"

            servicio = get_object_or_404(Servicio, id=servicio_id)
            empleado = get_object_or_404(Empleado, id=empleado_id)

            # Crear objetos datetime aware (con zona horaria)
            fecha_hora_str = f"{fecha_str} {hora_str}"
            fecha_naive = datetime.strptime(fecha_hora_str, "%Y-%m-%d %H:%M")
            fecha_inicio = timezone.make_aware(fecha_naive)
            
            # Calcular fin de la cita sumando la duración del servicio
            fecha_fin = fecha_inicio + servicio.duracion

            Cita.objects.create(
                peluqueria=peluqueria_actual,
                servicio=servicio,
                empleado=empleado,
                cliente_nombre=nombre,
                cliente_telefono=telefono,
                fecha_hora_inicio=fecha_inicio,
                fecha_hora_fin=fecha_fin
            )
            
            # Mensaje y Redirección Correcta
            messages.success(request, '¡Cita agendada con éxito!')
            return redirect('cita_confirmada') # <--- CORREGIDO: Redirige a la confirmación
            
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, 'salon/agendar.html', {
        'peluqueria': peluqueria_actual,
        'servicios': servicios,
        'empleados': empleados
    })

# --- API: CÁLCULO DE HORAS DISPONIBLES ---
def obtener_horas_disponibles(request):
    """
    Recibe: empleado_id, fecha, servicio_id
    Retorna: Lista de horas disponibles ej: ["09:00", "09:30", ...]
    """
    empleado_id = request.GET.get('empleado_id')
    fecha_str = request.GET.get('fecha')
    servicio_id = request.GET.get('servicio_id')

    if not (empleado_id and fecha_str and servicio_id):
        return JsonResponse({'error': 'Faltan datos'}, status=400)

    try:
        # 1. Obtener objetos necesarios
        empleado = Empleado.objects.get(id=empleado_id)
        servicio = Servicio.objects.get(id=servicio_id)
        peluqueria = empleado.peluqueria
        
        # Parsear fecha
        fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        dia_semana = fecha_obj.weekday() # Python: 0=Lunes, 6=Domingo (Coincide con models.py)

        # 2. Buscar horario del empleado para ESE día específico
        try:
            horario = HorarioSemanal.objects.get(empleado=empleado, dia_semana=dia_semana)
        except HorarioSemanal.DoesNotExist:
            return JsonResponse({'horas': [], 'mensaje': 'El estilista no trabaja este día.'})

        # 3. Definir límites de la jornada (Intersección Negocio vs Empleado)
        inicio_jornada = max(peluqueria.hora_apertura, horario.hora_inicio)
        fin_jornada = min(peluqueria.hora_cierre, horario.hora_fin)

        # 4. Obtener citas YA existentes que choquen ese día
        citas_existentes = Cita.objects.filter(
            empleado=empleado,
            fecha_hora_inicio__date=fecha_obj,
            estado__in=['P', 'C'] # Solo Pendientes o Confirmadas
        )

        # 5. Generar slots (bloques de tiempo) disponibles
        slots_disponibles = []
        tiempo_actual = datetime.combine(fecha_obj, inicio_jornada)
        limite_fin = datetime.combine(fecha_obj, fin_jornada)
        duracion_servicio = servicio.duracion

        # Bucle para probar cada intervalo de 30 mins
        while tiempo_actual + duracion_servicio <= limite_fin:
            hora_inicio_slot = tiempo_actual
            hora_fin_slot = tiempo_actual + duracion_servicio
            
            # A. Verificar Almuerzo
            en_almuerzo = False
            if horario.descanso_inicio and horario.descanso_fin:
                inicio_descanso = datetime.combine(fecha_obj, horario.descanso_inicio)
                fin_descanso = datetime.combine(fecha_obj, horario.descanso_fin)
                # Si el slot se solapa con el descanso
                if (hora_inicio_slot < fin_descanso and hora_fin_slot > inicio_descanso):
                    en_almuerzo = True

            # B. Verificar Colisión con Citas
            choca_cita = False
            if not en_almuerzo:
                inicio_aware = timezone.make_aware(hora_inicio_slot)
                fin_aware = timezone.make_aware(hora_fin_slot)
                
                for cita in citas_existentes:
                    # Fórmula de solapamiento de rangos
                    if (inicio_aware < cita.fecha_hora_fin) and (fin_aware > cita.fecha_hora_inicio):
                        choca_cita = True
                        break
            
            # Si pasa todas las pruebas, agregamos la hora
            if not choca_cita and not en_almuerzo:
                slots_disponibles.append(hora_inicio_slot.strftime("%H:%M"))

            # Avanzamos al siguiente bloque (intervalo de 30 mins)
            tiempo_actual += timedelta(minutes=30)

        return JsonResponse({'horas': slots_disponibles})

    except Exception as e:
        # En caso de error interno, devolver detalle para depurar
        return JsonResponse({'error': str(e)}, status=500)

def cita_confirmada(request):
    return render(request, 'salon/confirmacion.html')