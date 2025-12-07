from datetime import datetime, timedelta
from django.db.models import Q
from django.utils.timezone import make_aware 
from .models import Cita, HorarioSemanal, Ausencia

# ================================================================
# 🧠 CEREBRO DE DISPONIBILIDAD (Con soporte para Ausencias)
# ================================================================

def obtener_bloques_disponibles(empleado, fecha_consulta, duracion_total_servicios):
    """
    Calcula los horarios disponibles, manejando:
    1. Horario Laboral
    2. Citas existentes
    3. Ausencias (Vacaciones/Enfermedad)
    """
    
    # 0. VERIFICAR AUSENCIAS (NUEVO)
    # Si hay una ausencia que cubra la fecha de consulta, no hay cupos.
    esta_ausente = Ausencia.objects.filter(
        empleado=empleado,
        fecha_inicio__lte=fecha_consulta,
        fecha_fin__gte=fecha_consulta
    ).exists()

    if esta_ausente:
        return [] # El empleado está de vacaciones hoy

    # 1. ¿El empleado trabaja ese día de la semana?
    dia_semana = fecha_consulta.weekday()
    horario = HorarioSemanal.objects.filter(empleado=empleado, dia_semana=dia_semana).first()
    
    if not horario:
        return [] 

    horas_disponibles = []
    
    # Crear fechas base (Naive)
    inicio_naive = datetime.combine(fecha_consulta, horario.hora_inicio)
    fin_naive = datetime.combine(fecha_consulta, horario.hora_fin)

    # CONVERTIR A AWARE (Manejo de zonas horarias)
    try:
        hora_actual = make_aware(inicio_naive)
        fin_jornada = make_aware(fin_naive)
    except ValueError:
        hora_actual = inicio_naive
        fin_jornada = fin_naive
    
    # 2. Buscamos citas (La competencia)
    citas_del_dia = Cita.objects.filter(
        empleado=empleado,
        fecha_hora_inicio__date=fecha_consulta
    ).exclude(estado='A').values('fecha_hora_inicio', 'fecha_hora_fin')

    # 3. Barrido
    while hora_actual + duracion_total_servicios <= fin_jornada:
        fin_estimado = hora_actual + duracion_total_servicios
        esta_ocupado = False

        # A) Descanso
        if horario.descanso_inicio and horario.descanso_fin:
            ini_desc_naive = datetime.combine(fecha_consulta, horario.descanso_inicio)
            fin_desc_naive = datetime.combine(fecha_consulta, horario.descanso_fin)
            try:
                ini_desc = make_aware(ini_desc_naive)
                fin_desc = make_aware(fin_desc_naive)
            except ValueError:
                ini_desc = ini_desc_naive
                fin_desc = fin_desc_naive
            
            if (hora_actual < fin_desc) and (fin_estimado > ini_desc):
                esta_ocupado = True

        # B) Citas Existentes
        if not esta_ocupado:
            for cita in citas_del_dia:
                c_inicio = cita['fecha_hora_inicio']
                c_fin = cita['fecha_hora_fin']
                
                if (hora_actual < c_fin) and (fin_estimado > c_inicio):
                    esta_ocupado = True
                    break
        
        if not esta_ocupado:
            horas_disponibles.append(hora_actual.strftime("%H:%M"))
        
        hora_actual += timedelta(minutes=30)

    return horas_disponibles

def verificar_conflicto_atomic(empleado, inicio_nuevo, fin_nuevo):
    """
    Guardia de Seguridad: Verifica citas y también ausencias de última hora.
    """
    # 1. Verificar Citas
    choque_cita = Cita.objects.filter(
        empleado=empleado,
        fecha_hora_inicio__lt=fin_nuevo,
        fecha_hora_fin__gt=inicio_nuevo
    ).exclude(estado='A').exists()

    if choque_cita: return True

    # 2. Verificar Ausencias (Por si el dueño le dio vacaciones hace 1 segundo)
    fecha_dia = inicio_nuevo.date()
    choque_ausencia = Ausencia.objects.filter(
        empleado=empleado,
        fecha_inicio__lte=fecha_dia,
        fecha_fin__gte=fecha_dia
    ).exists()

    return choque_ausencia