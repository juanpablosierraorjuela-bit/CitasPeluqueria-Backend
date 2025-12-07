from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.db import transaction
from datetime import datetime
import json

from .models import Peluqueria, Servicio, Empleado, Cita
# Importamos el cerebro que acabamos de crear en el paso 1
from .services import obtener_bloques_disponibles, verificar_conflicto_atomic

# ================================================================
# 🔌 API (salon/api.py)
# ================================================================

def listar_servicios(request, slug_peluqueria):
    servicios = Servicio.objects.filter(peluqueria__slug=slug_peluqueria)
    data = list(servicios.values('id', 'nombre', 'duracion', 'precio'))
    # Convertimos datos complejos a simples para JSON
    for s in data:
        s['duracion'] = s['duracion'].total_seconds() / 60 
        s['precio'] = float(s['precio'])
    return JsonResponse(data, safe=False)

def listar_empleados(request, slug_peluqueria):
    empleados = Empleado.objects.filter(peluqueria__slug=slug_peluqueria)
    data = [{'id': e.id, 'nombre': f"{e.nombre} {e.apellido}"} for e in empleados]
    return JsonResponse(data, safe=False)

def consultar_disponibilidad(request, slug_peluqueria):
    """Devuelve SOLO los huecos donde SÍ se puede reservar."""
    fecha_str = request.GET.get('fecha')
    servicio_id = request.GET.get('service_id')
    empleado_id = request.GET.get('empleado_id') 

    if not (fecha_str and servicio_id):
        return JsonResponse({'error': 'Faltan datos'}, status=400)

    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        servicio = Servicio.objects.get(id=servicio_id)
        
        # Filtramos: ¿Un empleado específico o todos?
        if empleado_id and empleado_id != 'todos':
            empleados = [get_object_or_404(Empleado, id=empleado_id)]
        else:
            empleados = Empleado.objects.filter(peluqueria__slug=slug_peluqueria)

        resultados = {}
        for emp in empleados:
            # Usamos el cerebro para calcular
            horas = obtener_bloques_disponibles(emp, fecha, servicio.duracion)
            if horas:
                # Solo agregamos al empleado si tiene tiempo libre
                resultados[emp.nombre] = [{'hora_inicio': h} for h in horas]
        
        return JsonResponse(resultados)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def crear_cita_api(request, slug_peluqueria):
    """CREAR CITA DESDE LA APP (BLINDADO)"""
    if request.method != 'POST': return JsonResponse({'error': 'Solo POST'}, status=405)

    try:
        data = json.loads(request.body)
        peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)
        
        # Recuperar datos
        empleado = get_object_or_404(Empleado, id=data.get('empleado_id'))
        servicio = get_object_or_404(Servicio, id=data.get('servicio_id'))
        inicio = datetime.strptime(f"{data.get('fecha')} {data.get('hora_inicio')}", "%Y-%m-%d %H:%M")
        fin = inicio + servicio.duracion

        # 🛡️ BLINDAJE (Atomic Transaction)
        with transaction.atomic():
            # Preguntamos una última vez si está libre
            if verificar_conflicto_atomic(empleado, inicio, fin):
                return JsonResponse({'error': 'OCUPADO'}, status=409)

            # Si está libre, reservamos
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

        return JsonResponse({'mensaje': 'OK', 'id': cita.id}, status=201)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)