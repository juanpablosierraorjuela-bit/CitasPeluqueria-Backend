from datetime import timedelta, datetime
from django.utils import timezone
from .models import Cita, Ausencia, HorarioEmpleado

def obtener_bloques_disponibles(empleado, fecha_date, duracion_servicio):
    """
    Calcula los bloques libres basados en:
    1. Los horarios configurados en HorarioEmpleado para ese día de la semana.
    2. Las citas ya agendadas.
    3. Las ausencias (vacaciones/permisos).
    """
    # 1. Obtener el día de la semana (0=Lunes, 6=Domingo)
    dia_semana = fecha_date.weekday()
    
    # 2. Buscar los turnos de trabajo de ese día
    turnos = HorarioEmpleado.objects.filter(empleado=empleado, dia_semana=dia_semana).order_by('hora_inicio')
    
    if not turnos.exists():
        return [] # No trabaja este día

    bloques_disponibles = []

    # 3. Obtener citas y ausencias del día
    inicio_dia = timezone.make_aware(datetime.combine(fecha_date, datetime.min.time()))
    fin_dia = timezone.make_aware(datetime.combine(fecha_date, datetime.max.time()))
    
    citas = Cita.objects.filter(empleado=empleado, fecha_hora_inicio__range=(inicio_dia, fin_dia), estado__in=['C', 'P'])
    ausencias = Ausencia.objects.filter(empleado=empleado, fecha_inicio__lte=fin_dia, fecha_fin__gte=inicio_dia)

    # 4. Recorrer cada turno (ej: Mañana 9-12, Tarde 2-6)
    for turno in turnos:
        hora_actual = timezone.make_aware(datetime.combine(fecha_date, turno.hora_inicio))
        hora_fin_turno = timezone.make_aware(datetime.combine(fecha_date, turno.hora_fin))

        while hora_actual + duracion_servicio <= hora_fin_turno:
            fin_bloque = hora_actual + duracion_servicio
            ocupado = False

            # Verificar choques con citas
            for c in citas:
                if (hora_actual < c.fecha_hora_fin) and (fin_bloque > c.fecha_hora_inicio):
                    ocupado = True
                    break
            
            # Verificar choques con ausencias
            if not ocupado:
                for a in ausencias:
                    if (hora_actual < a.fecha_fin) and (fin_bloque > a.fecha_inicio):
                        ocupado = True
                        break
            
            if not ocupado:
                bloques_disponibles.append(hora_actual.strftime("%H:%M"))

            # Avanzamos 30 mins (intervalo estándar)
            hora_actual += timedelta(minutes=30)
            
    return bloques_disponibles

def verificar_conflicto_atomic(empleado, inicio, fin):
    # Verifica si hay solapamiento exacto en el momento de guardar (evita doble booking)
    return Cita.objects.filter(
        empleado=empleado,
        estado__in=['P', 'C'],
        fecha_hora_inicio__lt=fin,
        fecha_hora_fin__gt=inicio
    ).exists()
