from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.db.models import Sum
from django.utils.timezone import make_aware, now
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta
import hashlib
import traceback

from .models import Peluqueria, Servicio, Empleado, Cita
from .services import obtener_bloques_disponibles, verificar_conflicto_atomic

# 1. VISTA DE INICIO (Igual)
def inicio(request):
    peluquerias = Peluqueria.objects.all()
    return render(request, 'salon/index.html', {'peluquerias': peluquerias})

# 2. API HORARIOS (Igual)
def obtener_horas_disponibles(request):
    try:
        empleado_id = request.GET.get('empleado_id')
        fecha_str = request.GET.get('fecha')
        servicios_ids = request.GET.get('servicios_ids', '').split(',')

        if not (empleado_id and fecha_str and servicios_ids):
            return JsonResponse({'horas': []})

        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        empleado = get_object_or_404(Empleado, id=empleado_id)
        
        duracion_total = timedelta(minutes=0)
        for sid in servicios_ids:
            if sid:
                try:
                    s = Servicio.objects.get(id=sid)
                    duracion_total += s.duracion
                except: pass
        
        horas = obtener_bloques_disponibles(empleado, fecha, duracion_total)
        return JsonResponse({'horas': horas})

    except Exception as e:
        print(f"Error API Horarios: {e}")
        return JsonResponse({'horas': []})

# 3. AGENDAR CITA (MODIFICADA CON BOLD)
def agendar_cita(request, slug_peluqueria):
    peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)
    servicios = peluqueria.servicios.all()
    empleados = peluqueria.empleados.all()

    if request.method == 'POST':
        try:
            nombre = request.POST.get('nombre_cliente')
            telefono = request.POST.get('telefono_cliente')
            empleado_id = request.POST.get('empleado')
            fecha_str = request.POST.get('fecha_seleccionada')
            hora_str = request.POST.get('hora_seleccionada')
            servicios_ids = request.POST.getlist('servicios')

            if not (nombre and empleado_id and fecha_str and hora_str):
                raise ValueError("Faltan datos obligatorios")

            empleado = get_object_or_404(Empleado, id=empleado_id)
            fecha_naive = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
            try: inicio_cita = make_aware(fecha_naive) 
            except ValueError: inicio_cita = fecha_naive

            servicios_objs = Servicio.objects.filter(id__in=servicios_ids)
            duracion_total = sum([s.duracion for s in servicios_objs], timedelta())
            fin_cita = inicio_cita + duracion_total
            total_precio = sum([s.precio for s in servicios_objs])

            # --- LÓGICA HÍBRIDA: ¿COBRAR O NO COBRAR? ---
            usa_bold = bool(peluqueria.bold_api_key and peluqueria.bold_integrity_key)
            estado_inicial = 'P' if usa_bold else 'C' # P=Pendiente Pago, C=Confirmada

            with transaction.atomic():
                if verificar_conflicto_atomic(empleado, inicio_cita, fin_cita):
                    return render(request, 'salon/agendar.html', {
                        'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados,
                        'error_mensaje': f"⚠️ El horario de las {hora_str} ya no está disponible."
                    })
                
                cita = Cita.objects.create(
                    peluqueria=peluqueria,
                    cliente_nombre=nombre,
                    cliente_telefono=telefono,
                    empleado=empleado,
                    fecha_hora_inicio=inicio_cita,
                    fecha_hora_fin=fin_cita,
                    precio_total=total_precio,
                    estado=estado_inicial
                )
                cita.servicios.set(servicios_objs)

            # --- FLUJO DE DECISIÓN ---
            if usa_bold:
                # CASO 1: TIENE BOLD -> Redirigir a pago del 50%
                monto_anticipo = int(total_precio * 0.5)
                # Referencia única: CITA-{ID}-{TIMESTAMP}
                referencia = f"CITA-{cita.id}-{int(datetime.now().timestamp())}"
                cita.referencia_pago_bold = referencia
                cita.save()

                # Generar Firma de Integridad (SHA256)
                # Formato Bold: referencia + monto + moneda + secret
                cadena_concatenada = f"{referencia}{monto_anticipo}COP{peluqueria.bold_integrity_key}"
                signature = hashlib.sha256(cadena_concatenada.encode('utf-8')).hexdigest()

                return render(request, 'salon/pago_bold.html', {
                    'cita': cita,
                    'monto_anticipo': monto_anticipo,
                    'signature': signature,
                    'peluqueria': peluqueria,
                    'referencia': referencia
                })

            else:
                # CASO 2: NO TIENE BOLD -> Confirmar directo
                # Importante: Llamamos a Telegram AQUÍ, ya con los servicios guardados.
                cita.enviar_notificacion_telegram()
                return redirect('cita_confirmada')
            
        except Exception as e:
            traceback.print_exc()
            return render(request, 'salon/agendar.html', {'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados, 'error_mensaje': f"Error técnico: {str(e)}"})

    return render(request, 'salon/agendar.html', {
        'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados
    })

def cita_confirmada(request):
    return render(request, 'salon/confirmacion.html')

# 4. RETORNO BOLD (NUEVO)
@csrf_exempt 
def retorno_bold(request):
    """Aquí llega el usuario después de pagar en Bold"""
    status = request.GET.get('tx_status') # approved, rejected, failed
    referencia = request.GET.get('reference')

    if not referencia: return redirect('inicio')

    try:
        cita = Cita.objects.get(referencia_pago_bold=referencia)
        
        if status == 'approved':
            cita.estado = 'C' # Confirmada
            cita.abono_pagado = cita.precio_total * 0.5 
            cita.save() 
            
            # ¡PAGO EXITOSO! AHORA SÍ ENVIAMOS LA NOTIFICACIÓN COMPLETA
            cita.enviar_notificacion_telegram()
            
            return redirect('cita_confirmada')
        
        elif status == 'rejected' or status == 'failed':
            cita.estado = 'A' # Anulada (libera el horario)
            cita.save()
            return HttpResponse("<h1>Pago Rechazado o Fallido</h1><a href='/'>Volver al inicio</a>")
        
        else:
            return HttpResponse("<h1>Estado del pago pendiente...</h1>")

    except Cita.DoesNotExist:
        return redirect('inicio')

# 5. DASHBOARD Y MANIFEST (Igual)
@login_required(login_url='/admin/login/')
def dashboard_dueño(request):
    try: peluqueria = request.user.perfil.peluqueria
    except: peluqueria = None

    if not peluqueria:
        if request.user.is_superuser: peluqueria = Peluqueria.objects.first()
        if not peluqueria: return render(request, 'salon/error_dashboard.html', {'mensaje': 'Sin peluquería'})

    hoy = now().date()
    citas_hoy = Cita.objects.filter(peluqueria=peluqueria, fecha_hora_inicio__date=hoy).count()
    ingresos_mes = Cita.objects.filter(peluqueria=peluqueria, fecha_hora_inicio__month=hoy.month, estado='C').aggregate(Sum('precio_total'))['precio_total__sum'] or 0
    proximas_citas = Cita.objects.filter(peluqueria=peluqueria, fecha_hora_inicio__gte=now(), estado='C').order_by('fecha_hora_inicio')[:5]

    context = {'peluqueria': peluqueria, 'citas_hoy': citas_hoy, 'ingresos_mes': ingresos_mes, 'proximas_citas': proximas_citas}
    return render(request, 'salon/dashboard.html', context)

def manifest_view(request):
    manifest_data = {
        "name": "Citas Peluquería",
        "short_name": "Mi Salón",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#ec4899",
        "orientation": "portrait",
        "icons": [
            {"src": "https://cdn-icons-png.flaticon.com/512/3899/3899618.png", "sizes": "192x192", "type": "image/png"},
            {"src": "https://cdn-icons-png.flaticon.com/512/3899/3899618.png", "sizes": "512x512", "type": "image/png"}
        ]
    }
    return JsonResponse(manifest_data)
