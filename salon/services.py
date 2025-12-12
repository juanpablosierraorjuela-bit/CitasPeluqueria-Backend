import pytz
from datetime import timedelta, datetime
from django.utils import timezone
from .models import Cita, Ausencia, HorarioEmpleado

# Intervalo de los bloques de tiempo (cada cuánto inicia una cita)
INTERVALO_MINUTOS = 30

def obtener_bloques_disponibles(empleado, fecha_date, duracion_servicio):
    """
    Calcula los bloques de inicio disponibles para un servicio de X duración.
    """
    dia_semana = fecha_date.weekday() # 0=Lunes, 6=Domingo
    
    # Zona Horaria Colombia para evitar desfases
    zona_co = pytz.timezone('America/Bogota')

    try:
        horario = HorarioEmpleado.objects.get(empleado=empleado, dia_semana=dia_semana)
    except HorarioEmpleado.DoesNotExist:
        return []

    bloques = []
    
    # 1. Crear fechas con Zona Horaria Correcta (Colombia)
    inicio_turno = timezone.make_aware(datetime.combine(fecha_date, horario.hora_inicio), zona_co)
    fin_turno = timezone.make_aware(datetime.combine(fecha_date, horario.hora_fin), zona_co)
    
    inicio_almuerzo = None
    fin_almuerzo = None
    if horario.almuerzo_inicio and horario.almuerzo_fin:
        inicio_almuerzo = timezone.make_aware(datetime.combine(fecha_date, horario.almuerzo_inicio), zona_co)
        fin_almuerzo = timezone.make_aware(datetime.combine(fecha_date, horario.almuerzo_fin), zona_co)

    # 2. Obtener Citas y Ausencias que SOLAPEN con el turno
    citas = Cita.objects.filter(
        empleado=empleado, 
        estado__in=['C', 'P'], 
        fecha_hora_fin__gt=inicio_turno,
        fecha_hora_inicio__lt=fin_turno
    )
    
    ausencias = Ausencia.objects.filter(
        empleado=empleado, 
        fecha_fin__gt=inicio_turno,
        fecha_inicio__lt=fin_turno
    )

    hora_actual = inicio_turno

    # 3. Iterar bloques
    while hora_actual + duracion_servicio <= fin_turno:
        fin_bloque = hora_actual + duracion_servicio
        ocupado = False

        if inicio_almuerzo and fin_almuerzo:
            if (hora_actual < fin_almuerzo) and (fin_bloque > inicio_almuerzo):
                ocupado = True

        if not ocupado:
            for c in citas:
                if (hora_actual < c.fecha_hora_fin) and (fin_bloque > c.fecha_hora_inicio):
                    ocupado = True; break
        
        if not ocupado:
            for a in ausencias:
                if (hora_actual < a.fecha_fin) and (fin_bloque > a.fecha_inicio):
                    ocupado = True; break
            
        if not ocupado: 
            bloques.append(hora_actual.strftime("%H:%M"))
        
        hora_actual += timedelta(minutes=INTERVALO_MINUTOS)
            
    return bloques

def verificar_conflicto_atomic(empleado, inicio, fin):
    return Cita.objects.filter(
        empleado=empleado, 
        estado__in=['P', 'C'],
        fecha_hora_inicio__lt=fin, 
        fecha_hora_fin__gt=inicio
    ).exists()
