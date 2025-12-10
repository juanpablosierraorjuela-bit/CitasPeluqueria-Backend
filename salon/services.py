from datetime import timedelta, datetime, time
from django.utils import timezone
from .models import Cita, Ausencia, HorarioEmpleado

# CORRECCIÓN: Definir un intervalo de agendamiento. Usamos 15 minutos para mayor granularidad.
INTERVALO_MINUTOS = 15

def obtener_bloques_disponibles(empleado, fecha_date, duracion_servicio):
    dia_semana = fecha_date.weekday() # 0=Lunes, 6=Domingo
    
    # 1. Buscamos el horario específico del empleado para ese día de la semana
    try:
        horario = HorarioEmpleado.objects.get(empleado=empleado, dia_semana=dia_semana)
    except HorarioEmpleado.DoesNotExist:
        # Si no tiene horario configurado en la base de datos para este día, devuelve lista vacía (sin cupos)
        return []

    bloques = []
    
    # Usamos las horas reales configuradas en la base de datos
    inicio_turno = timezone.make_aware(datetime.combine(fecha_date, horario.hora_inicio))
    fin_turno = timezone.make_aware(datetime.combine(fecha_date, horario.hora_fin))
    
    # Definir almuerzo si existe
    inicio_almuerzo = None
    fin_almuerzo = None
    if horario.almuerzo_inicio and horario.almuerzo_fin:
        inicio_almuerzo = timezone.make_aware(datetime.combine(fecha_date, horario.almuerzo_inicio))
        fin_almuerzo = timezone.make_aware(datetime.combine(fecha_date, horario.almuerzo_fin))

    # Obtenemos citas y ausencias para filtrar
    citas = Cita.objects.filter(
        empleado=empleado, 
        fecha_hora_inicio__gte=inicio_turno, 
        fecha_hora_inicio__lt=fin_turno,
        estado__in=['C', 'P']
    )
    ausencias = Ausencia.objects.filter(
        empleado=empleado, 
        fecha_inicio__lte=fin_turno, 
        fecha_fin__gte=inicio_turno
    )

    hora_actual = inicio_turno

    while hora_actual + duracion_servicio <= fin_turno:
        fin_bloque = hora_actual + duracion_servicio
        ocupado = False

        # 1. Verificar Almuerzo
        if inicio_almuerzo and fin_almuerzo:
            # Si el bloque choca con el almuerzo (inicia antes de que termine y termina después de que inicie)
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
        # Usar el intervalo configurable (antes estaba en 30 minutos fijo)
        hora_actual += timedelta(minutes=INTERVALO_MINUTOS)
            
    return bloques

def verificar_conflicto_atomic(empleado, inicio, fin):
    return Cita.objects.filter(empleado=empleado, estado__in=['P', 'C'], fecha_hora_inicio__lt=fin, fecha_hora_fin__gt=inicio).exists()
