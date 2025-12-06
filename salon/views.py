import requests 
from django.shortcuts import render, redirect, get_object_or_404
from .models import Cita, Peluqueria, Servicio, Empleado
from datetime import datetime

# --- VISTA DE INICIO (LA QUE FALTABA) ---
def inicio(request):
    # Traemos todas las peluquerías para mostrarlas en el home
    peluquerias = Peluqueria.objects.all()
    return render(request, 'salon/index.html', {'peluquerias': peluquerias})

# --- FUNCIÓN DE TELEGRAM ---
def enviar_notificacion_telegram(cita):
    try:
        # Limpieza de datos
        peluqueria = cita.peluqueria
        token = str(peluqueria.telegram_token).strip() if peluqueria.telegram_token else None
        chat_id = str(peluqueria.telegram_chat_id).strip() if peluqueria.telegram_chat_id else None

        print(f"--- 🚀 INTENTANDO ENVIAR A: {peluqueria.nombre_visible} ---")
        print(f"--- DATOS: Token=...{token[-5:] if token else 'N/A'} | ChatID={chat_id} ---")

        if not token or not chat_id:
            print("❌ ERROR: Faltan credenciales (Token o ID).")
            return False

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

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = { "chat_id": chat_id, "text": mensaje, "parse_mode": "Markdown" }

        response = requests.post(url, data=data, timeout=10)
        res = response.json()

        if response.status_code == 200 and res.get('ok'):
            print(f"✅ ÉXITO TELEGRAM: Mensaje entregado.")
            return True
        else:
            print(f"❌ FALLO TELEGRAM: {res}")
            return False

    except Exception as e:
        print(f"❌ ERROR CRITICO: {str(e)}")
        return False


# --- VISTA PRINCIPAL DE AGENDAR ---
def agendar_cita(request, slug):
    # ESTE ES EL PRINT QUE OBLIGARÁ A RENDER A MOSTRARNOS QUE ESTÁ VIVO
    print(f"\n🌟🌟🌟 INICIANDO PROCESO DE AGENDA PARA: {slug} 🌟🌟🌟\n")
    
    peluqueria = get_object_or_404(Peluqueria, slug=slug)
    servicios = peluqueria.servicios.all()
    empleados = peluqueria.empleados.all()

    if request.method == 'POST':
        print("📝 Recibiendo formulario POST...")
        nombre = request.POST.get('nombre_cliente')
        telefono = request.POST.get('telefono_cliente')
        empleado_id = request.POST.get('empleado')
        fecha_str = request.POST.get('fecha_seleccionada')
        hora_str = request.POST.get('hora_seleccionada')
        servicios_ids = request.POST.getlist('servicios')

        if not (nombre and telefono and empleado_id and fecha_str and hora_str and servicios_ids):
            print("⚠️ Faltan datos en el formulario")
            return render(request, 'agendar.html', {'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados, 'error': 'Faltan datos'})

        empleado = get_object_or_404(Empleado, id=empleado_id)
        fecha_hora_inicio = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
        
        servicios_objs = Servicio.objects.filter(id__in=servicios_ids)
        total = sum([s.precio for s in servicios_objs])

        # Crear cita CONFIRMADA 'C'
        cita = Cita.objects.create(
            peluqueria=peluqueria,
            cliente_nombre=nombre,
            cliente_telefono=telefono,
            empleado=empleado,
            fecha_hora_inicio=fecha_hora_inicio,
            fecha_hora_fin=fecha_hora_inicio, 
            precio_total=total,
            estado='C' 
        )
        cita.servicios.set(servicios_objs)
        print(f"💾 Cita guardada ID: {cita.id}")

        # LLAMADA EXPLÍCITA A TELEGRAM
        enviar_notificacion_telegram(cita)

        return render(request, 'confirmacion.html')

    return render(request, 'agendar.html', {'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados})

def respuesta_bold(request):
    return render(request, 'confirmacion.html')