# UBICACIÓN: salon/api.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.conf import settings
from datetime import datetime
import json

from .models import Peluqueria, Servicio, Empleado, Cita
from .services import obtener_bloques_disponibles, verificar_conflicto_atomic
# IMPORTAMOS AL GUARDIA
from salon.utils.booking_lock import BookingManager

def proteger_api(vista_func):
    """Decorador simple para verificar la API Key"""
    def _wrapped_view(request, *args, **kwargs):
        api_key_recibida = request.headers.get('X-API-KEY')
        if api_key_recibida != settings.API_SECRET_KEY:
            return JsonResponse({'error': 'Acceso denegado: API Key inválida o faltante'}, status=403)
        return vista_func(request, *args, **kwargs)
    return _wrapped_view

@proteger_api
def listar_servicios(request, slug_peluqueria):
    servicios = Servicio.objects.filter(peluqueria__slug=slug_peluqueria)
    data = list(servicios.values('id', 'nombre', 'duracion', 'precio'))
    for s in data:
        s['duracion'] = s['duracion'].total_seconds() / 60 
        s['precio'] = float(s['precio'])
    return JsonResponse(data, safe=False)

@proteger_api
def listar_empleados(request, slug_peluqueria):
    empleados = Empleado.objects.filter(peluqueria__slug=slug_peluqueria, activo=True)
    data = [{'id': e.id, 'nombre': f"{e.nombre} {e.apellido}"} for e in empleados]
    return JsonResponse(data, safe=False)

@proteger_api
def consultar_disponibilidad(request, slug_peluqueria):
    fecha_str = request.GET.get('fecha')
    servicio_id = request.GET.get('service_id')
    empleado_id = request.GET.get('empleado_id') 

    if not (fecha_str and servicio_id):
        return JsonResponse({'error': 'Faltan parámetros fecha o service_id'}, status=400)

    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        servicio = get_object_or_404(Servicio, id=servicio_id)
        
        # Filtro de empleados
        if empleado_id and empleado_id != 'todos': 
            empleados = Empleado.objects.filter(id=empleado_id, activo=True)
        else: 
            empleados = Empleado.objects.filter(peluqueria__slug=slug_peluqueria, activo=True)

        resultados = {}
        for emp in empleados:
            # Usamos la duración del servicio seleccionado para calcular bloques
            horas = obtener_bloques_disponibles(emp, fecha, servicio.duracion)
            if horas: 
                resultados[emp.nombre] = [{'hora_inicio': h} for h in horas]
        
        return JsonResponse(resultados)
    except ValueError:
        return JsonResponse({'error': 'Formato de fecha inválido. Use YYYY-MM-DD'}, status=400)
    except Exception as e:
        print(f"Error API: {e}") 
        return JsonResponse({'error': 'Error interno del servidor'}, status=500)

@csrf_exempt
@proteger_api
def crear_cita_api(request, slug_peluqueria):
    if request.method != 'POST': 
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
        peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)
        
        # Obtenemos IDs básicos
        empleado_id = data.get('empleado_id')
        servicio_id = data.get('servicio_id')
        servicio = get_object_or_404(Servicio, id=servicio_id)
        
        # Parseo seguro de fecha y hora
        fecha_str = data.get('fecha')
        hora_str = data.get('hora_inicio')
        inicio = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
        fin = inicio + servicio.duracion

        # --- DEFINICIÓN DE LA LÓGICA SEGURA ---
        # Esta función se ejecutará DENTRO del bloqueo del Guardia
        def _logica_crear_cita(empleado_bloqueado, *args, **kwargs):
            # Validar pertenencia
            if empleado_bloqueado.peluqueria != peluqueria:
                raise ValueError('El empleado no pertenece a esta peluquería')

            # 1. Verificar conflicto (Ahora es 100% seguro porque nadie más puede escribir)
            if verificar_conflicto_atomic(empleado_bloqueado, inicio, fin):
                # Lanzamos error específico para capturarlo fuera
                raise ValueError('HORARIO_OCUPADO')

            # 2. Crear Cita
            nueva_cita = Cita.objects.create(
                peluqueria=peluqueria,
                empleado=empleado_bloqueado,
                cliente_nombre=data.get('cliente_nombre', 'Cliente App'),
                cliente_telefono=data.get('cliente_telefono', '0000000000'),
                fecha_hora_inicio=inicio,
                fecha_hora_fin=fin,
                precio_total=servicio.precio,
                estado='C' # Confirmada directamente (Pago en local asumido para API)
            )
            # 3. Asociar servicio (M2M)
            nueva_cita.servicios.add(servicio)
            return nueva_cita

        # --- EJECUCIÓN CON EL GUARDIA ---
        # Le decimos al Guardia: "Bloquea a este empleado y ejecuta esta lógica"
        cita = BookingManager.ejecutar_reserva_segura(empleado_id, _logica_crear_cita)
        
        # Notificar fuera de la transacción
        cita.enviar_notificacion_telegram()

        return JsonResponse({'mensaje': 'Cita creada exitosamente', 'id': cita.id}, status=201)

    except ValueError as ve:
        mensaje = str(ve)
        if 'HORARIO_OCUPADO' in mensaje:
            return JsonResponse({'error': 'HORARIO_OCUPADO'}, status=409)
        return JsonResponse({'error': f'Error de validación: {mensaje}'}, status=400)
    except Exception as e:
        print(f"Error API Crear Cita: {e}")
        return JsonResponse({'error': str(e)}, status=500)
