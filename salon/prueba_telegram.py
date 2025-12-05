from django.http import JsonResponse
from .models import Servicio, Empleado, Cita, HorarioSemanal 
from django.db.models import Q
from datetime import datetime, timedelta
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
import requests # Mantenemos requests por si lo usas en otras APIs, aunque ya no es necesario aquí.

# --- CONFIGURACIÓN DE DÍAS ---
# Diccionario para mapear el número del día de Python (0=Lun)
DIA_MAPPING = {
    0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, # Usamos números directamente, como en models.py
}

# La función enviar_notificacion_telegram y las credenciales FINAL_TOKEN/FINAL_CHAT_ID DEBEN SER ELIMINADAS.
# La notificación será manejada por la Señal en models.py.
# ------------------------------------------------------------------------


# API 1: Servicios
def listar_servicios(request, slug_peluqueria): # Agregamos el slug para el Multi-tenant
    """Retorna una lista de servicios disponibles para la peluquería por SLUG."""
    try:
        servicios = Servicio.objects.filter(peluqueria__slug=slug_peluqueria)
        lista_servicios = list(servicios.values('id', 'nombre', 'duracion', 'precio')) # Corregimos a 'duracion'
        return JsonResponse(lista_servicios, safe=False)
    except Exception as e:
        return JsonResponse({'error': f'Error listando servicios: {str(e)}'}, status=500)


# API 2: Empleados
def listar_empleados(request, slug_peluqueria): # Agregamos el slug para el Multi-tenant
    """Retorna una lista de empleados para la peluquería por SLUG."""
    empleados = Empleado.objects.filter(peluqueria__slug=slug_peluqueria)
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
def verificar_disponibilidad(request, slug_peluqueria): # Agregamos el slug para el Multi-tenant
    """
    Verifica los horarios libres usando el modelo HorarioSemanal.
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Solo se permiten peticiones GET'}, status=405)

    try:
        # Aquí también necesitas filtrar por peluquería si esta API se usara
        # service_id = request.GET.get('service_id')
        # ... (La lógica de disponibilidad es compleja y debe reescribirse para el MultiTenant) ...

        return JsonResponse({'mensaje': 'La lógica de disponibilidad requiere más datos (fecha, servicio) y fue simplificada en este ejemplo. Consulta la vista principal.'}, safe=False)


    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# API 4: Creación de Cita (El Candado)
@csrf_exempt
@require_POST
def crear_cita(request, slug_peluqueria): # Agregamos el slug para el Multi-tenant
    """Recibe los datos, VERIFICA DISPONIBILIDAD, y guarda la cita."""
    try:
        data = json.loads(request.body)
        
        # 1. Datos básicos (deberían venir del formulario web, no ser hardcodeados)
        cliente_nombre = data.get('cliente_nombre', "Cliente App") 
        cliente_telefono = data.get('cliente_telefono', "0000000000")
        servicios_ids = data.get('servicios_ids', []) # Ahora es una lista de IDs
        
        # 2. Datos de la reserva
        empleado_id = data.get('empleado_id')
        fecha_hora_inicio_str = data.get('fecha_hora_inicio')
        fecha_hora_fin_str = data.get('fecha_hora_fin')

        if not empleado_id or not fecha_hora_inicio_str or not servicios_ids:
             return JsonResponse({'error': 'Faltan datos de la reserva'}, status=400)

        # Objetos de DB
        empleado = Empleado.objects.get(id=empleado_id, peluqueria__slug=slug_peluqueria)
        servicios_a_reservar = Servicio.objects.filter(id__in=servicios_ids)

        # Fechas exactas
        fecha_hora_inicio = datetime.strptime(fecha_hora_inicio_str, "%Y-%m-%d %H:%M")
        fecha_hora_fin = datetime.strptime(fecha_hora_fin_str, "%Y-%m-%d %H:%M")
        
        # ------------------------------------------------------------------
        # 🚫 VALIDACIÓN DE DISPONIBILIDAD (EL CANDADO)
        existe_conflicto = Cita.objects.filter(
            empleado=empleado,
            fecha_hora_inicio__lt=fecha_hora_fin, 
            fecha_hora_fin__gt=fecha_hora_inicio,
        ).exists()

        if existe_conflicto:
            return JsonResponse({'error': f'Lo sentimos, {empleado.nombre} ya fue reservado en ese horario.'}, status=400)
        # ------------------------------------------------------------------

        # 3. SI ESTÁ LIBRE, GUARDAMOS
        cita = Cita.objects.create(
            peluqueria=empleado.peluqueria,
            cliente_nombre=cliente_nombre,
            cliente_telefono=cliente_telefono,
            empleado=empleado,
            fecha_hora_inicio=fecha_hora_inicio,
            fecha_hora_fin=fecha_hora_fin,
            estado='P' # Marcamos como Pendiente
        )
        
        # Guardamos los servicios (Esto dispara la señal de Telegram en models.py)
        cita.servicios.set(servicios_a_reservar)
        
        # Calculamos y guardamos el precio total (Lógica no incluida, pero necesaria)
        # cita.precio_total = sum(s.precio for s in servicios_a_reservar)
        # cita.save() 
        
        # 4. ELIMINAMOS LA LLAMADA TELEGRAM (La señal de models.py lo hará automáticamente)

        return JsonResponse({'mensaje': 'Cita reservada con éxito!', 'id': cita.id}, status=201)

    except Empleado.DoesNotExist:
        return JsonResponse({'error': 'Empleado o Peluquería no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Error en el proceso de reserva: {str(e)}'}, status=500)