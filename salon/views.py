import requests # IMPORTANTE: Necesario para enviar a Telegram
from django.shortcuts import render, redirect, get_object_or_404
from .models import Cita, Peluqueria, Servicio, Empleado
from datetime import datetime

# --- FUNCIÓN AUXILIAR DE TELEGRAM (A PRUEBA DE FALLOS) ---
def enviar_notificacion_telegram(cita):
    """
    Envía el mensaje inmediatamente sin depender de señales automáticas.
    Imprime errores en la consola para depurar en Render.
    """
    try:
        # 1. Obtener datos y limpiar espacios vacíos
        peluqueria = cita.peluqueria
        token = str(peluqueria.telegram_token).strip() if peluqueria.telegram_token else None
        chat_id = str(peluqueria.telegram_chat_id).strip() if peluqueria.telegram_chat_id else None

        # LOG PARA RENDER: Esto saldrá en tu consola de Render
        print(f"--- INTENTANDO ENVIAR TELEGRAM A {peluqueria.nombre_visible} ---")
        
        if not token or not chat_id:
            print(f"❌ ERROR: Faltan credenciales en la peluquería {peluqueria.nombre_visible}.")
            return False

        # 2. Armar el mensaje con los datos de la cita
        servicios_nombres = ", ".join([s.nombre for s in cita.servicios.all()])
        
        mensaje = (
            f"🔔 *NUEVA CITA AGENDADA*\n\n"
            f"👤 *Cliente:* {cita.cliente_nombre}\n"
            f"📞 *Tel:* {cita.cliente_telefono}\n"
            f"📅 *Fecha:* {cita.fecha_hora_inicio.strftime('%d/%m/%Y')}\n"
            f"⏰ *Hora:* {cita.fecha_hora_inicio.strftime('%H:%M')}\n"
            f"💇 *Servicios:* {servicios_nombres}\n"
            f"✂️ *Estilista:* {cita.empleado.nombre} {cita.empleado.apellido}\n"
            f"💰 *Valor:* ${cita.precio_total}\n"
        )

        # 3. Enviar petición directa a la API de Telegram
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": mensaje,
            "parse_mode": "Markdown"
        }

        response = requests.post(url, data=data, timeout=10)
        respuesta_json = response.json()

        if response.status_code == 200 and respuesta_json.get('ok'):
            print(f"✅ ÉXITO: Mensaje entregado al Chat ID {chat_id}")
            return True
        else:
            # Aquí verás por qué falló (ej: Chat not found, Unauthorized, etc.)
            print(f"❌ FALLÓ TELEGRAM: {respuesta_json}")
            return False

    except Exception as e:
        print(f"❌ ERROR CRÍTICO EN TELEGRAM: {str(e)}")
        return False


# --- VISTA PRINCIPAL DE AGENDAMIENTO ---
def agendar_cita(request, slug):
    peluqueria = get_object_or_404(Peluqueria, slug=slug)
    
    # Obtenemos servicios y empleados para pintar el formulario
    servicios = peluqueria.servicios.all()
    empleados = peluqueria.empleados.all()

    if request.method == 'POST':
        # 1. Recoger datos del formulario
        nombre = request.POST.get('nombre_cliente')
        telefono = request.POST.get('telefono_cliente')
        empleado_id = request.POST.get('empleado')
        fecha_str = request.POST.get('fecha_seleccionada') # "2023-10-25"
        hora_str = request.POST.get('hora_seleccionada')   # "14:00"
        servicios_ids = request.POST.getlist('servicios') # Lista de IDs ['1', '4']

        # Validaciones básicas
        if not (nombre and telefono and empleado_id and fecha_str and hora_str and servicios_ids):
            return render(request, 'agendar.html', {'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados, 'error': 'Faltan datos'})

        # 2. Crear los objetos necesarios
        empleado = get_object_or_404(Empleado, id=empleado_id)
        fecha_hora_inicio = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
        fecha_hora_fin = fecha_hora_inicio # (Aquí podrías sumar duración si quisieras)

        # 3. Calcular precio total
        servicios_objs = Servicio.objects.filter(id__in=servicios_ids)
        total = sum([s.precio for s in servicios_objs])

        # 4. GUARDAR LA CITA
        cita = Cita.objects.create(
            peluqueria=peluqueria,
            cliente_nombre=nombre,
            cliente_telefono=telefono,
            empleado=empleado,
            fecha_hora_inicio=fecha_hora_inicio,
            fecha_hora_fin=fecha_hora_fin,
            precio_total=total,
            estado='C' # Confirmada directamente
        )
        
        # Guardar la relación Muchos-a-Muchos
        cita.servicios.set(servicios_objs)

        # ==============================================================================
        # AQUÍ ESTÁ LA SOLUCIÓN: LLAMADA EXPLÍCITA (OBLIGATORIA)
        # Forzamos el envío del mensaje YA MISMO.
        # ==============================================================================
        enviar_notificacion_telegram(cita)
        # ==============================================================================

        # Redirigir a confirmación
        return render(request, 'confirmacion.html')

    # GET: Mostrar formulario
    return render(request, 'agendar.html', {
        'peluqueria': peluqueria, 
        'servicios': servicios,
        'empleados': empleados
    })