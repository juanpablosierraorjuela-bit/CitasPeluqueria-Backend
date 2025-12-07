from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db import transaction
from datetime import datetime, timedelta

from .models import Peluqueria, Servicio, Empleado, Cita
# IMPORTE CLAVE: Traemos la lógica del archivo services.py que creamos en el Paso 1
from .services import obtener_bloques_disponibles, verificar_conflicto_atomic
# (Opcional) Si tienes el archivo de notificaciones
try:
    from .prueba_telegram import enviar_notificacion_telegram 
except ImportError:
    def enviar_notificacion_telegram(cita): pass

# 1. INICIO
def inicio(request):
    peluquerias = Peluqueria.objects.all()
    return render(request, 'salon/index.html', {'peluquerias': peluquerias})

# 2. API INTERNA (Para el HTML)
def obtener_horas_disponibles(request):
    """
    Esta vista la usa el navegador web para mostrar los botones de hora.
    """
    try:
        empleado_id = request.GET.get('empleado_id')
        fecha_str = request.GET.get('fecha')
        servicios_ids = request.GET.get('servicios_ids', '').split(',')

        if not (empleado_id and fecha_str and servicios_ids):
            return JsonResponse({'horas': []})

        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        empleado = get_object_or_404(Empleado, id=empleado_id)
        
        # Sumar duraciones
        duracion_total = timedelta(minutes=0)
        for sid in servicios_ids:
            if sid:
                try:
                    s = Servicio.objects.get(id=sid)
                    duracion_total += s.duracion
                except: pass
        
        # USAMOS EL CEREBRO (services.py) en lugar de recalcular todo aquí
        horas = obtener_bloques_disponibles(empleado, fecha, duracion_total)
        
        return JsonResponse({'horas': horas})

    except Exception as e:
        return JsonResponse({'horas': []})

# 3. AGENDAR CITA (POST WEB - BLINDADO)
def agendar_cita(request, slug_peluqueria):
    peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)
    servicios = peluqueria.servicios.all()
    empleados = peluqueria.empleados.all()

    if request.method == 'POST':
        try:
            # Recibir datos del formulario
            nombre = request.POST.get('nombre_cliente')
            telefono = request.POST.get('telefono_cliente')
            empleado_id = request.POST.get('empleado')
            fecha_str = request.POST.get('fecha_seleccionada')
            hora_str = request.POST.get('hora_seleccionada')
            servicios_ids = request.POST.getlist('servicios')

            # Validar
            if not (nombre and empleado_id and fecha_str and hora_str):
                raise ValueError("Faltan datos")

            empleado = get_object_or_404(Empleado, id=empleado_id)
            inicio_cita = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
            
            # Calcular fin
            servicios_objs = Servicio.objects.filter(id__in=servicios_ids)
            duracion_total = sum([s.duracion for s in servicios_objs], timedelta())
            fin_cita = inicio_cita + duracion_total
            total_precio = sum([s.precio for s in servicios_objs])

            # 🛡️ AQUÍ ESTÁ EL BLINDAJE (Atomic Transaction)
            with transaction.atomic():
                # El sistema se "congela" un instante para verificar
                if verificar_conflicto_atomic(empleado, inicio_cita, fin_cita):
                    # Si falla, devolvemos error visual
                    return render(request, 'salon/agendar.html', {
                        'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados,
                        'error_mensaje': f"⚠️ Lo sentimos, las {hora_str} ya no está disponible."
                    })
                
                # Si pasa, guardamos seguro
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
            
            # Notificar (fuera del bloqueo)
            try: enviar_notificacion_telegram(cita)
            except: pass
            
            return redirect('cita_confirmada')
            
        except Exception as e:
            return render(request, 'salon/agendar.html', {
                'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados,
                'error_mensaje': 'Error procesando solicitud.'
            })

    return render(request, 'salon/agendar.html', {
        'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados
    })

def cita_confirmada(request):
    return render(request, 'salon/confirmacion.html')