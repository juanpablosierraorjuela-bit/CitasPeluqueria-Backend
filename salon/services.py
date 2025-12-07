from datetime import datetime, timedelta
from django.db.models import Q
from django.utils.timezone import make_aware # IMPORTANTE
from .models import Cita, HorarioSemanal

# ================================================================
# 🧠 CEREBRO DE DISPONIBILIDAD (Corregido: Zonas Horarias)
# ================================================================

def obtener_bloques_disponibles(empleado, fecha_consulta, duracion_total_servicios):
    """
    Calcula los horarios disponibles, manejando correctamente las zonas horarias.
    """
    
    # 1. ¿El empleado trabaja ese día?
    dia_semana = fecha_consulta.weekday()
    horario = HorarioSemanal.objects.filter(empleado=empleado, dia_semana=dia_semana).first()
    
    if not horario:
        return [] 

    horas_disponibles = []
    
    # Crear fechas base (Naive)
    inicio_naive = datetime.combine(fecha_consulta, horario.hora_inicio)
    fin_naive = datetime.combine(fecha_consulta, horario.hora_fin)

    # CONVERTIR A AWARE (Consciente de zona horaria) para comparar con DB
    try:
        hora_actual = make_aware(inicio_naive)
        fin_jornada = make_aware(fin_naive)
    except ValueError:
        # Si ya tienen zona horaria (raro, pero posible), las usamos tal cual
        hora_actual = inicio_naive
        fin_jornada = fin_naive
    
    # 2. Buscamos citas (La competencia)
    # Traemos fechas que YA son aware desde Django
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
            # Convertimos a aware para comparar con hora_actual
            ini_desc = make_aware(ini_desc_naive)
            fin_desc = make_aware(fin_desc_naive)
            
            if (hora_actual < fin_desc) and (fin_estimado > ini_desc):
                esta_ocupado = True

        # B) Citas Existentes (Comparación Aware vs Aware)
        if not esta_ocupado:
            for cita in citas_del_dia:
                c_inicio = cita['fecha_hora_inicio']
                c_fin = cita['fecha_hora_fin']
                
                if (hora_actual < c_fin) and (fin_estimado > c_inicio):
                    esta_ocupado = True
                    break
        
        if not esta_ocupado:
            # Guardamos solo la hora string (limpio)
            horas_disponibles.append(hora_actual.strftime("%H:%M"))
        
        hora_actual += timedelta(minutes=30)

    return horas_disponibles

def verificar_conflicto_atomic(empleado, inicio_nuevo, fin_nuevo):
    """
    El Guardia de Seguridad. 
    Recibe fechas 'inicio_nuevo' y 'fin_nuevo' que DEBEN ser Aware.
    """
    return Cita.objects.filter(
        empleado=empleado,
        fecha_hora_inicio__lt=fin_nuevo,
        fecha_hora_fin__gt=inicio_nuevo
    ).exclude(estado='A').exists()