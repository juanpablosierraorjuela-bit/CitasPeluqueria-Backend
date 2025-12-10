# UBICACIÓN: salon/services.py
from datetime import timedelta, datetime, time
from django.utils import timezone
from .models import Cita, Ausencia, HorarioEmpleado

# Intervalo de los bloques de tiempo en minutos (Ej: cada 15 min muestra disponibilidad)
INTERVALO_MINUTOS = 15

def obtener_bloques_disponibles(empleado, fecha_date, duracion_servicio):
    """
    Calcula los bloques de inicio disponibles para un servicio de X duración.
    """
    dia_semana = fecha_date.weekday() # 0=Lunes, 6=Domingo
    
    # 1. Buscamos el horario específico del empleado para ese día
    try:
        horario = HorarioEmpleado.objects.get(empleado=empleado, dia_semana=dia_semana)
    except HorarioEmpleado.DoesNotExist:
        return []

    bloques = []
    
    # Convertimos horas simples a datetime con zona horaria
    inicio_turno = timezone.make_aware(datetime.combine(fecha_date, horario.hora_inicio))
    fin_turno = timezone.make_aware(datetime.combine(fecha_date, horario.hora_fin))
    
    # Definir almuerzo si existe
    inicio_almuerzo = None
    fin_almuerzo = None
    if horario.almuerzo_inicio and horario.almuerzo_fin:
        inicio_almuerzo = timezone.make_aware(datetime.combine(fecha_date, horario.almuerzo_inicio))
        fin_almuerzo = timezone.make_aware(datetime.combine(fecha_date, horario.almuerzo_fin))

    # Obtenemos citas y ausencias existentes para filtrar
    citas = Cita.objects.filter(
        empleado=empleado, 
        fecha_hora_inicio__gte=inicio_turno, 
        fecha_hora_inicio__lt=fin_turno,
        estado__in=['C', 'P'] # Confirmadas o Pendientes bloquean el espacio
    )
    ausencias = Ausencia.objects.filter(
        empleado=empleado, 
        fecha_inicio__lte=fin_turno, 
        fecha_fin__gte=inicio_turno
    )

    hora_actual = inicio_turno

    # Iteramos cada X minutos para buscar huecos
    while hora_actual + duracion_servicio <= fin_turno:
        fin_bloque = hora_actual + duracion_servicio
        ocupado = False

        # 1. Verificar Choque con Almuerzo
        if inicio_almuerzo and fin_almuerzo:
            if (hora_actual < fin_almuerzo) and (fin_bloque > inicio_almuerzo):
                ocupado = True

        # 2. Verificar Choque con Citas existentes
        if not ocupado:
            for c in citas:
                # Lógica de superposición: (InicioA < FinB) y (FinA > InicioB)
                if (hora_actual < c.fecha_hora_fin) and (fin_bloque > c.fecha_hora_inicio):
                    ocupado = True; break
        
        # 3. Verificar Choque con Ausencias
        if not ocupado:
            for a in ausencias:
                if (hora_actual < a.fecha_fin) and (fin_bloque > a.fecha_inicio):
                    ocupado = True; break
            
        if not ocupado: bloques.append(hora_actual.strftime("%H:%M"))
        
        hora_actual += timedelta(minutes=INTERVALO_MINUTOS)
            
    return bloques

def verificar_conflicto_atomic(empleado, inicio, fin):
    """
    Verifica si existe alguna cita superpuesta en el rango dado.
    Esta función se debe llamar DENTRO de una transacción atómica.
    """
    return Cita.objects.filter(
        empleado=empleado, 
        estado__in=['P', 'C'], # P=Pendiente, C=Confirmada
        fecha_hora_inicio__lt=fin, 
        fecha_hora_fin__gt=inicio
    ).exists()
