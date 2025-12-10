from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.conf import settings
from datetime import datetime
import json

from .models import Peluqueria, Servicio, Empleado, Cita
from .services import obtener_bloques_disponibles, verificar_conflicto_atomic

def proteger_api(vista_func):
    def _wrapped_view(request, *args, **kwargs):
        api_key_recibida = request.headers.get('X-API-KEY')
        if api_key_recibida != settings.API_SECRET_KEY:
            return JsonResponse({'error': 'Acceso denegado'}, status=403)
        return vista_func(request, *args, **kwargs)
    return _wrapped_view

@proteger_api # <--- CRÍTICO: Agregado
def listar_servicios(request, slug_peluqueria):
    servicios = Servicio.objects.filter(peluqueria__slug=slug_peluqueria)
    data = list(servicios.values('id', 'nombre', 'duracion', 'precio'))
    for s in data:
        s['duracion'] = s['duracion'].total_seconds() / 60 
        s['precio'] = float(s['precio'])
    return JsonResponse(data, safe=False)

@proteger_api # <--- CRÍTICO: Agregado
def listar_empleados(request, slug_peluqueria):
    empleados = Empleado.objects.filter(peluqueria__slug=slug_peluqueria)
    data = [{'id': e.id, 'nombre': f"{e.nombre} {e.apellido}"} for e in empleados]
    return JsonResponse(data, safe=False)

@proteger_api # <--- CRÍTICO: Agregado
def consultar_disponibilidad(request, slug_peluqueria):
    fecha_str = request.GET.get('fecha')
    servicio_id = request.GET.get('service_id')
    empleado_id = request.GET.get('empleado_id') 

    if not (fecha_str and servicio_id): return JsonResponse({'error': 'Faltan datos'}, status=400)

    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        servicio = Servicio.objects.get(id=servicio_id)
        if empleado_id and empleado_id != 'todos': empleados = [get_object_or_404(Empleado, id=empleado_id)]
        else: empleados = Empleado.objects.filter(peluqueria__slug=slug_peluqueria)

        resultados = {}
        for emp in empleados:
            horas = obtener_bloques_disponibles(emp, fecha, servicio.duracion)
            if horas: resultados[emp.nombre] = [{'hora_inicio': h} for h in horas]
        
        return JsonResponse(resultados)
    except Exception as e:
        print(f"Error API: {e}") 
        return JsonResponse({'error': 'Error interno'}, status=500)

@csrf_exempt
@proteger_api
def crear_cita_api(request, slug_peluqueria):
    if request.method != 'POST': return JsonResponse({'error': 'Solo POST'}, status=405)

    try:
        data = json.loads(request.body)
        peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)
        empleado = get_object_or_404(Empleado, id=data.get('empleado_id'))
        servicio = get_object_or_404(Servicio, id=data.get('servicio_id'))
        
        inicio = datetime.strptime(f"{data.get('fecha')} {data.get('hora_inicio')}", "%Y-%m-%d %H:%M")
        fin = inicio + servicio.duracion

        with transaction.atomic():
            if verificar_conflicto_atomic(empleado, inicio, fin):
                return JsonResponse({'error': 'OCUPADO'}, status=409)

            cita = Cita.objects.create(
                peluqueria=peluqueria,
                empleado=empleado,
                cliente_nombre=data.get('cliente_nombre', 'App User'),
                cliente_telefono=data.get('cliente_telefono', '000'),
                fecha_hora_inicio=inicio,
                fecha_hora_fin=fin,
                precio_total=servicio.precio,
                estado='C'
            )
            cita.servicios.add(servicio)
        
        # NOTIFICAR MANUALMENTE (Para que salgan los servicios)
        cita.enviar_notificacion_telegram()

        return JsonResponse({'mensaje': 'OK', 'id': cita.id}, status=201)

    except Exception as e:
        print(f"Error API Crear Cita: {e}")
        return JsonResponse({'error': str(e)}, status=500)
