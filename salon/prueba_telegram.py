from django.http import JsonResponse
from .models import Servicio, Empleado, Cita, HorarioSemanal 
from django.db.models import Q
from datetime import datetime, timedelta
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
import requests

# --- CONFIGURACIÓN GLOBAL ---
# Diccionario para mapear el número del día de Python (0=Lun) al texto de nuestro modelo (LUN)
DIA_MAPPING = {
    0: 'LUN', 1: 'MAR', 2: 'MIE', 3: 'JUE', 4: 'VIE', 5: 'SAB', 6: 'DOM',
}

# TUS CREDENCIALES FINALES
FINAL_TOKEN = "8430924416:AAHFNIRrU4RjZyrW8gzoZwEKwGKwhx-0G8E"
FINAL_CHAT_ID = "8203009135"

# --- FUNCIÓN TELEGRAM ---
def enviar_notificacion_telegram(nombre_cliente, fecha, hora, empleado):
    mensaje = f"🔔 *NUEVA CITA RESERVADA*\n\n👤 Cliente: {nombre_cliente}\n📅 Fecha: {fecha}\n⏰ Hora: {hora}\n💇‍♀️ Con: {empleado}"
    url = f"https://api.telegram.org/bot{FINAL_TOKEN}/sendMessage"
    data = {"chat_id": FINAL_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    
    try:
        requests.post(url, data=data)
        print("✅ Notificación enviada a Telegram")
    except Exception as e:
        print(f"❌ Error enviando Telegram: {e}")
# ------------------------------------------------------------------------


# API 1: Servicios
def listar_servicios(request):
    """Retorna una lista de todos los servicios disponibles."""
    servicios = Servicio.objects.all()
    lista_servicios = list(servicios.values('id', 'nombre', 'duracion_minutos', 'precio'))
    return JsonResponse(lista_servicios, safe=False)

# API 2: Empleados
def listar_empleados(request):
    """Retorna una lista de todos los empleados."""
    empleados = Empleado.objects.all()
    lista_empleados = []
    
    for empleado in empleados:
        empleado_dict = {
            'id': empleado.id,
            'nombre': empleado.nombre,
            'apellido': empleado.apellido,
            'servicios_ids': list(empleado.servicios_que_realiza.values_list('id', flat=True))
        }
        lista_empleados.append(empleado_dict)
        
    return JsonResponse(lista_empleados, safe=False)

# API 3: Verificación de Disponibilidad (LÓGICA SEMANAL FINAL)
def verificar_disponibilidad(request):
    """
    Verifica los horarios libres usando el nuevo modelo HorarioSemanal.
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Solo se permiten peticiones GET'}, status=405)

    try:
        service_id = request.GET.get('service_id')
        fecha_str = request.GET.get('fecha')
        
        if not service_id or not fecha_str:
            return JsonResponse({'error': 'Faltan parámetros: service_id o fecha.'}, status=400)

        servicio = Servicio.objects.get(id=service_id)
        duracion_servicio = servicio.duracion_minutos

        fecha_cita = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        
        # 1. Obtenemos el día de la semana para la consulta (ej: 'MIE')
        dia_de_la_semana_num = fecha_cita.weekday()
        dia_abreviado = DIA_MAPPING.get(dia_de_la_semana_num)

        empleados_elegibles = Empleado.objects.filter(servicios_que_realiza__id=service_id)
        
        horarios_disponibles = {}
        
        for empleado in empleados_elegibles:
            
            # 2. BUSCAMOS EL HORARIO ESPECÍFICO PARA ESE DÍA
            horario_del_dia = empleado.horarios_semanales.filter(dia_semana=dia_abreviado).first()
            
            # Si no tiene horario ese día, lo saltamos.
            if not horario_del_dia:
                continue
                
            hora_inicio_laboral = datetime.combine(fecha_cita, horario_del_dia.hora_inicio)
            hora_fin_laboral = datetime.combine(fecha_cita, horario_del_dia.hora_fin)
            
            # --- Lógica de generación de slots ---
            disponibilidad_empleado = []
            hora_actual = hora_inicio_laboral
            
            while hora_actual + timedelta(minutes=duracion_servicio) <= hora_fin_laboral:
                
                hora_fin_tentativa = hora_actual + timedelta(minutes=duracion_servicio)

                conflicto = Cita.objects.filter(
                    empleado=empleado,
                    fecha_hora_inicio__date=fecha_cita,
                    fecha_hora_inicio__lt=hora_fin_tentativa, 
                    fecha_hora_fin__gt=hora_actual
                ).exists()

                if not conflicto:
                    disponibilidad_empleado.append({
                        'hora_inicio': hora_actual.strftime('%H:%M'),
                        'hora_fin': hora_fin_tentativa.strftime('%H:%M'),
                        'empleado_id': empleado.id
                    })
                
                hora_actual += timedelta(minutes=30) 

            if disponibilidad_empleado:
                horarios_disponibles[empleado.nombre] = disponibilidad_empleado

        return JsonResponse(horarios_disponibles, safe=False)

    except Servicio.DoesNotExist:
        return JsonResponse({'error': 'Servicio no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# API 4: Creación de Cita (El Candado y Telegram)
@csrf_exempt
@require_POST
def crear_cita(request):
    """Recibe los datos, VERIFICA DISPONIBILIDAD, guarda y avisa."""
    try:
        data = json.loads(request.body)
        
        # 1. Datos básicos
        cliente_nombre = "Cliente App" 
        cliente_telefono = "0000000000"
        
        # 2. Datos de la reserva
        servicio_id = data.get('servicio_id')
        empleado_id = data.get('empleado_id')
        hora_inicio_str = data.get('hora_inicio')
        hora_fin_str = data.get('hora_fin')
        fecha_str = data.get('fecha') 

        # Objetos de DB
        servicio = Servicio.objects.get(id=servicio_id)
        empleado = Empleado.objects.get(id=empleado_id)
        
        # Fechas exactas
        fecha_hora_inicio = datetime.strptime(f"{fecha_str} {hora_inicio_str}", "%Y-%m-%d %H:%M")
        fecha_hora_fin = datetime.strptime(f"{fecha_str} {hora_fin_str}", "%Y-%m-%d %H:%M")
        
        # ------------------------------------------------------------------
        # 🚫 VALIDACIÓN DE DISPONIBILIDAD (EL CANDADO)
        existe_conflicto = Cita.objects.filter(
            empleado=empleado,
            fecha_hora_inicio=fecha_hora_inicio
        ).exists()

        if existe_conflicto:
            return JsonResponse({'error': f'Lo sentimos, {empleado.nombre} ya fue reservado a las {hora_inicio_str}.'}, status=400)
        # ------------------------------------------------------------------

        # 3. SI ESTÁ LIBRE, GUARDAMOS
        cita = Cita.objects.create(
            cliente_nombre=cliente_nombre,
            cliente_telefono=cliente_telefono,
            servicio=servicio,
            empleado=empleado,
            fecha_hora_inicio=fecha_hora_inicio,
            fecha_hora_fin=fecha_hora_fin,
            estado='C'
        )

        # 4. ENVIAMOS TELEGRAM
        try:
            enviar_notificacion_telegram(
                nombre_cliente=cliente_nombre,
                fecha=fecha_str,
                hora=hora_inicio_str,
                empleado=empleado.nombre
            )
        except Exception as e_tg:
            print(f"⚠️ Cita guardada, pero falló Telegram: {e_tg}")

        return JsonResponse({'mensaje': 'Cita reservada con éxito!', 'id': cita.id}, status=201)

    except Empleado.DoesNotExist:
        return JsonResponse({'error': 'Empleado no encontrado'}, status=404)
    except Servicio.DoesNotExist:
        return JsonResponse({'error': 'Servicio no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Error: {str(e)}'}, status=500)