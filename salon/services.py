from datetime import datetime, timedelta
from django.db.models import Q
from .models import Cita, HorarioSemanal

# ================================================================
# 🧠 CEREBRO DE DISPONIBILIDAD (services.py)
# ================================================================

def obtener_bloques_disponibles(empleado, fecha_consulta, duracion_total_servicios):
    """
    Calcula los horarios disponibles para un empleado en una fecha específica.
    """
    
    # 1. ¿El empleado trabaja ese día de la semana?
    dia_semana = fecha_consulta.weekday()
    horario = HorarioSemanal.objects.filter(empleado=empleado, dia_semana=dia_semana).first()
    
    if not horario:
        return [] # No trabaja hoy

    horas_disponibles = []
    
    # Definimos límites del día
    hora_actual = datetime.combine(fecha_consulta, horario.hora_inicio)
    fin_jornada = datetime.combine(fecha_consulta, horario.hora_fin)
    
    # 2. Buscamos todas las citas confirmadas de ese día (La competencia)
    citas_del_dia = Cita.objects.filter(
        empleado=empleado,
        fecha_hora_inicio__date=fecha_consulta
    ).exclude(estado='A').values('fecha_hora_inicio', 'fecha_hora_fin')

    # 3. Barrido: Vamos probando cada 30 minutos
    while hora_actual + duracion_total_servicios <= fin_jornada:
        fin_estimado = hora_actual + duracion_total_servicios
        esta_ocupado = False

        # A) ¿Choca con la hora del almuerzo?
        if horario.descanso_inicio and horario.descanso_fin:
            ini_descanso = datetime.combine(fecha_consulta, horario.descanso_inicio)
            fin_descanso = datetime.combine(fecha_consulta, horario.descanso_fin)
            
            if (hora_actual < fin_descanso) and (fin_estimado > ini_descanso):
                esta_ocupado = True

        # B) ¿Choca con alguna cita existente?
        if not esta_ocupado:
            for cita in citas_del_dia:
                # Quitamos la zona horaria para poder comparar números planos
                c_inicio = cita['fecha_hora_inicio'].replace(tzinfo=None)
                c_fin = cita['fecha_hora_fin'].replace(tzinfo=None)
                
                # Fórmula de Colisión: ¿Se solapan los tiempos?
                if (hora_actual < c_fin) and (fin_estimado > c_inicio):
                    esta_ocupado = True
                    break
        
        # 4. Si sobrevivió a todas las pruebas, ¡es un hueco libre!
        if not esta_ocupado:
            horas_disponibles.append(hora_actual.strftime("%H:%M"))
        
        # Avanzamos al siguiente bloque de 30 min
        hora_actual += timedelta(minutes=30)

    return horas_disponibles

def verificar_conflicto_atomic(empleado, inicio_nuevo, fin_nuevo):
    """
    Verifica una última vez si hay choque justo antes de guardar.
    Retorna True si YA está ocupado.
    """
    return Cita.objects.filter(
        empleado=empleado,
        fecha_hora_inicio__lt=fin_nuevo,
        fecha_hora_fin__gt=inicio_nuevo
    ).exclude(estado='A').exists()