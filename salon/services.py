# UBICACIÓN: salon/services.py
from datetime import timedelta, datetime
from django.utils import timezone
from .models import Cita, Ausencia, HorarioEmpleado
import pytz

# Intervalo de los bloques de tiempo (15 min)
INTERVALO_MINUTOS = 30 # Lo cambié a 30 para coincidir con tu vista, o déjalo en 15 si prefieres granularidad

def obtener_bloques_disponibles(empleado, fecha_date, duracion_servicio):
    """
    Calcula los bloques de inicio disponibles para un servicio de X duración.
    """
    dia_semana = fecha_date.weekday() # 0=Lunes, 6=Domingo
    
    # Zona Horaria Colombia
    zona_co = pytz.timezone('America/Bogota')

    try:
        horario = HorarioEmpleado.objects.get(empleado=empleado, dia_semana=dia_semana)
    except HorarioEmpleado.DoesNotExist:
        return []

    bloques = []
    
    # 1. Crear fechas con Zona Horaria Correcta (Colombia)
    # make_aware sin segundo argumento usa la del sistema (a veces UTC), forzamos Colombia
    inicio_turno = timezone.make_aware(datetime.combine(fecha_date, horario.hora_inicio), zona_co)
    fin_turno = timezone.make_aware(datetime.combine(fecha_date, horario.hora_fin), zona_co)
    
    inicio_almuerzo = None
    fin_almuerzo = None
    if horario.almuerzo_inicio and horario.almuerzo_fin:
        inicio_almuerzo = timezone.make_aware(datetime.combine(fecha_date, horario.almuerzo_inicio), zona_co)
        fin_almuerzo = timezone.make_aware(datetime.combine(fecha_date, horario.almuerzo_fin), zona_co)

    # 2. Filtrar Citas que se solapen con el turno (CORREGIDO)
    # Buscamos citas que terminen DESPUES de que empiece el turno Y empiecen ANTES de que termine
    citas = Cita.objects.filter(
        empleado=empleado, 
        estado__in=['C', 'P'], # Confirmadas o Pendientes bloquean el espacio
        fecha_hora_fin__gt=inicio_turno,   # Terminan después del inicio del turno
        fecha_hora_inicio__lt=fin_turno    # Empiezan antes del fin del turno
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

        # Verificar Choque con Almuerzo
        if inicio_almuerzo and fin_almuerzo:
            # Si el bloque toca el almuerzo (se solapa)
            if (hora_actual < fin_almuerzo) and (fin_bloque > inicio_almuerzo):
                ocupado = True

        # Verificar Choque con Citas existentes
        if not ocupado:
            for c in citas:
                # Lógica estricta de solapamiento:
                # El bloque actual se solapa con la cita si:
                # (InicioBloque < FinCita) Y (FinBloque > InicioCita)
                if (hora_actual < c.fecha_hora_fin) and (fin_bloque > c.fecha_hora_inicio):
                    ocupado = True; break
        
        # Verificar Choque con Ausencias
        if not ocupado:
            for a in ausencias:
                if (hora_actual < a.fecha_fin) and (fin_bloque > a.fecha_inicio):
                    ocupado = True; break
            
        if not ocupado: 
            bloques.append(hora_actual.strftime("%H:%M"))
        
        hora_actual += timedelta(minutes=15) # Intervalo de saltos
            
    return bloques
