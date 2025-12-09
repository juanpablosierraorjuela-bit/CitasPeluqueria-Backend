from datetime import timedelta, datetime
from django.utils import timezone
from .models import Cita, Ausencia, HorarioEmpleado

def obtener_bloques_disponibles(empleado, fecha_date, duracion_servicio):
    dia_semana = fecha_date.weekday()
    turnos = HorarioEmpleado.objects.filter(empleado=empleado, dia_semana=dia_semana).order_by('hora_inicio')
    
    if not turnos.exists(): return []

    bloques = []
    inicio_dia = timezone.make_aware(datetime.combine(fecha_date, datetime.min.time()))
    fin_dia = timezone.make_aware(datetime.combine(fecha_date, datetime.max.time()))
    
    citas = Cita.objects.filter(empleado=empleado, fecha_hora_inicio__range=(inicio_dia, fin_dia), estado__in=['C', 'P'])
    ausencias = Ausencia.objects.filter(empleado=empleado, fecha_inicio__lte=fin_dia, fecha_fin__gte=inicio_dia)

    for turno in turnos:
        hora_actual = timezone.make_aware(datetime.combine(fecha_date, turno.hora_inicio))
        hora_fin_turno = timezone.make_aware(datetime.combine(fecha_date, turno.hora_fin))

        while hora_actual + duracion_servicio <= hora_fin_turno:
            fin_bloque = hora_actual + duracion_servicio
            ocupado = False
            for c in citas:
                if (hora_actual < c.fecha_hora_fin) and (fin_bloque > c.fecha_hora_inicio):
                    ocupado = True; break
            if not ocupado:
                for a in ausencias:
                    if (hora_actual < a.fecha_fin) and (fin_bloque > a.fecha_inicio):
                        ocupado = True; break
            
            if not ocupado: bloques.append(hora_actual.strftime("%H:%M"))
            hora_actual += timedelta(minutes=30)
            
    return bloques

def verificar_conflicto_atomic(empleado, inicio, fin):
    return Cita.objects.filter(empleado=empleado, estado__in=['P', 'C'], fecha_hora_inicio__lt=fin, fecha_hora_fin__gt=inicio).exists()
