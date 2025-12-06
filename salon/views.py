import requests 
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from datetime import datetime, timedelta
from .models import Cita, Peluqueria, Servicio, Empleado, HorarioSemanal

# 1. VISTA DE INICIO
def inicio(request):
    peluquerias = Peluqueria.objects.all()
    return render(request, 'salon/index.html', {'peluquerias': peluquerias})

# 2. API PARA CALCULAR HORARIOS DISPONIBLES (ESTA FALTABA)
def obtener_horas_disponibles(request):
    try:
        empleado_id = request.GET.get('empleado_id')
        fecha_str = request.GET.get('fecha')
        servicios_ids = request.GET.get('servicios_ids', '').split(',')

        if not (empleado_id and fecha_str and servicios_ids):
            return JsonResponse({'horas': []})

        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        empleado = get_object_or_404(Empleado, id=empleado_id)
        
        # Calcular duración total de los servicios
        duracion_total = timedelta(minutes=0)
        for sid in servicios_ids:
            if sid:
                try:
                    s = Servicio.objects.get(id=sid)
                    duracion_total += s.duracion
                except: pass

        # Buscar el horario del empleado para ese día de la semana (0=Lunes, 6=Domingo)
        dia_semana = fecha.weekday()
        horario = HorarioSemanal.objects.filter(empleado=empleado, dia_semana=dia_semana).first()
        
        if not horario:
            return JsonResponse({'horas': []}) # No trabaja ese día

        # Generar bloques de tiempo
        horas_disponibles = []
        hora_actual = datetime.combine(fecha, horario.hora_inicio)
        fin_jornada = datetime.combine(fecha, horario.hora_fin)
        
        # Buscar citas existentes para no chocar
        citas_existentes = Cita.objects.filter(
            empleado=empleado, 
            fecha_hora_inicio__date=fecha
        ).exclude(estado='A') # Ignoramos anuladas

        while hora_actual + duracion_total <= fin_jornada:
            fin_estimado = hora_actual + duracion_total
            ocupado = False

            # Verificar descanso
            if horario.descanso_inicio and horario.descanso_fin:
                ini_desc = datetime.combine(fecha, horario.descanso_inicio)
                fin_desc = datetime.combine(fecha, horario.descanso_fin)
                # Si el bloque choca con el descanso
                if hora_actual < fin_desc and fin_estimado > ini_desc:
                    ocupado = True

            # Verificar citas existentes
            if not ocupado:
                for c in citas_existentes:
                    # Lógica de colisión de rangos
                    # inicio_cita < fin_estimado Y fin_cita > hora_actual
                    c_inicio = c.fecha_hora_inicio.replace(tzinfo=None)
                    c_fin = c.fecha_hora_fin.replace(tzinfo=None)
                    
                    if c_inicio < fin_estimado and c_fin > hora_actual:
                        ocupado = True
                        break
            
            if not ocupado:
                horas_disponibles.append(hora_actual.strftime("%H:%M"))
            
            # Saltos de 30 minutos
            hora_actual += timedelta(minutes=30)

        return JsonResponse({'horas': horas_disponibles})

    except Exception as e:
        print(f"Error API: {e}")
        return JsonResponse({'horas': []})

# 3. NOTIFICACIÓN TELEGRAM
def enviar_notificacion_telegram(cita):
    try:
        peluqueria = cita.peluqueria
        token = str(peluqueria.telegram_token).strip() if peluqueria.telegram_token else None
        chat_id = str(peluqueria.telegram_chat_id).strip() if peluqueria.telegram_chat_id else None

        print(f"--- 🚀 TELEGRAM: Enviando a {peluqueria.nombre_visible} ---")
        
        if not token or not chat_id:
            print("❌ TELEGRAM: Faltan credenciales.")
            return False

        servicios_nombres = ", ".join([s.nombre for s in cita.servicios.all()])
        
        mensaje = (
            f"🔔 *NUEVA CITA CONFIRMADA*\n\n"
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

        requests.post(url, data=data, timeout=5)
        print("✅ TELEGRAM: Enviado.")
        return True

    except Exception as e:
        print(f"❌ TELEGRAM ERROR: {str(e)}")
        return False

# 4. AGENDAR CITA
def agendar_cita(request, slug):
    print(f"🌟 Iniciando Agendar: {slug}")
    peluqueria = get_object_or_404(Peluqueria, slug=slug)
    
    if request.method == 'POST':
        try:
            nombre = request.POST.get('nombre_cliente')
            telefono = request.POST.get('telefono_cliente')
            empleado_id = request.POST.get('empleado')
            fecha_str = request.POST.get('fecha_seleccionada')
            hora_str = request.POST.get('hora_seleccionada')
            servicios_ids = request.POST.getlist('servicios')

            if not (nombre and empleado_id and fecha_str and hora_str):
                raise ValueError("Faltan datos")

            empleado = get_object_or_404(Empleado, id=empleado_id)
            inicio_cita = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
            
            # Calcular fin de cita real
            servicios_objs = Servicio.objects.filter(id__in=servicios_ids)
            duracion_total = sum([s.duracion for s in servicios_objs], timedelta())
            fin_cita = inicio_cita + duracion_total
            total_precio = sum([s.precio for s in servicios_objs])

            cita = Cita.objects.create(
                peluqueria=peluqueria,
                cliente_nombre=nombre,
                cliente_telefono=telefono,
                empleado=empleado,
                fecha_hora_inicio=inicio_cita,
                fecha_hora_fin=fin_cita,
                precio_total=total_precio,
                estado='C'
            )
            cita.servicios.set(servicios_objs)
            
            # Disparar Telegram
            enviar_notificacion_telegram(cita)
            
            return render(request, 'confirmacion.html')
            
        except Exception as e:
            print(f"Error al agendar: {e}")
            # Volver a cargar formulario con error
            return render(request, 'agendar.html', {
                'peluqueria': peluqueria, 
                'servicios': peluqueria.servicios.all(),
                'empleados': peluqueria.empleados.all()
            })

    return render(request, 'agendar.html', {
        'peluqueria': peluqueria, 
        'servicios': peluqueria.servicios.all(),
        'empleados': peluqueria.empleados.all()
    })

# Vista extra por si acaso
def respuesta_bold(request):
    return render(request, 'confirmacion.html')