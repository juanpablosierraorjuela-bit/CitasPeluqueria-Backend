from datetime import timedelta, datetime, time
from django.utils import timezone
# Eliminamos HorarioEmpleado de la importación
from .models import Cita, Ausencia

def obtener_bloques_disponibles(empleado, fecha_date, duracion_servicio):
    dia_semana = fecha_date.weekday()
    
    # COMO YA NO EXISTE EL MODELO DE HORARIOS, USAMOS UN HORARIO POR DEFECTO:
    # Lunes (0) a Sábado (5): Trabajan de 9:00 a 18:00
    # Domingo (6): No trabajan
    if dia_semana == 6: # Domingo cerrado
        return []

    # Horario fijo temporal (Hardcoded)
    hora_inicio_turno = time(9, 0)
    hora_fin_turno = time(18, 0)
    almuerzo_inicio_turno = time(13, 0)
    almuerzo_fin_turno = time(14, 0)

    bloques = []
    inicio_dia = timezone.make_aware(datetime.combine(fecha_date, datetime.min.time()))
    fin_dia = timezone.make_aware(datetime.combine(fecha_date, datetime.max.time()))
    
    citas = Cita.objects.filter(empleado=empleado, fecha_hora_inicio__range=(inicio_dia, fin_dia), estado__in=['C', 'P'])
    ausencias = Ausencia.objects.filter(empleado=empleado, fecha_inicio__lte=fin_dia, fecha_fin__gte=inicio_dia)

    # Definir límites del turno con los valores fijos
    hora_actual = timezone.make_aware(datetime.combine(fecha_date, hora_inicio_turno))
    hora_fin_turno_dt = timezone.make_aware(datetime.combine(fecha_date, hora_fin_turno))

    # Definir almuerzo
    inicio_almuerzo = timezone.make_aware(datetime.combine(fecha_date, almuerzo_inicio_turno))
    fin_almuerzo = timezone.make_aware(datetime.combine(fecha_date, almuerzo_fin_turno))

    while hora_actual + duracion_servicio <= hora_fin_turno_dt:
        fin_bloque = hora_actual + duracion_servicio
        ocupado = False

        # 1. Verificar Almuerzo
        if (hora_actual < fin_almuerzo) and (fin_bloque > inicio_almuerzo):
            ocupado = True

        # 2. Verificar Citas
        if not ocupado:
            for c in citas:
                if (hora_actual < c.fecha_hora_fin) and (fin_bloque > c.fecha_hora_inicio):
                    ocupado = True; break
        
        # 3. Verificar Ausencias
        if not ocupado:
            for a in ausencias:
                if (hora_actual < a.fecha_fin) and (fin_bloque > a.fecha_inicio):
                    ocupado = True; break
            
        if not ocupado: bloques.append(hora_actual.strftime("%H:%M"))
        hora_actual += timedelta(minutes=30)
            
    return bloques

def verificar_conflicto_atomic(empleado, inicio, fin):
    return Cita.objects.filter(empleado=empleado, estado__in=['P', 'C'], fecha_hora_inicio__lt=fin, fecha_hora_fin__gt=inicio).exists()
