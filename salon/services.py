from datetime import timedelta, datetime
from django.utils import timezone
from .models import Cita, Ausencia, HorarioEmpleado

def obtener_bloques_disponibles(empleado, fecha_date, duracion_servicio):
    dia_semana = fecha_date.weekday()
    # Buscamos el turno único de ese día
    turno = HorarioEmpleado.objects.filter(empleado=empleado, dia_semana=dia_semana).first()
    
    if not turno: return []

    bloques = []
    inicio_dia = timezone.make_aware(datetime.combine(fecha_date, datetime.min.time()))
    fin_dia = timezone.make_aware(datetime.combine(fecha_date, datetime.max.time()))
    
    citas = Cita.objects.filter(empleado=empleado, fecha_hora_inicio__range=(inicio_dia, fin_dia), estado__in=['C', 'P'])
    ausencias = Ausencia.objects.filter(empleado=empleado, fecha_inicio__lte=fin_dia, fecha_fin__gte=inicio_dia)

    # Definir límites del turno
    hora_actual = timezone.make_aware(datetime.combine(fecha_date, turno.hora_inicio))
    hora_fin_turno = timezone.make_aware(datetime.combine(fecha_date, turno.hora_fin))

    # Definir almuerzo si existe
    inicio_almuerzo = None
    fin_almuerzo = None
    if turno.almuerzo_inicio and turno.almuerzo_fin:
        inicio_almuerzo = timezone.make_aware(datetime.combine(fecha_date, turno.almuerzo_inicio))
        fin_almuerzo = timezone.make_aware(datetime.combine(fecha_date, turno.almuerzo_fin))

    while hora_actual + duracion_servicio <= hora_fin_turno:
        fin_bloque = hora_actual + duracion_servicio
        ocupado = False

        # 1. Verificar Almuerzo
        if inicio_almuerzo and fin_almuerzo:
            # Si el bloque choca con el intervalo de almuerzo
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
