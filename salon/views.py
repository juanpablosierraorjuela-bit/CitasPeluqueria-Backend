from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.db.models import Sum
from django.utils.timezone import make_aware, now
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta
from decimal import Decimal # <--- 1. IMPORTANTE: Agregamos esto
import hashlib
import traceback

from .models import Peluqueria, Servicio, Empleado, Cita
from .services import obtener_bloques_disponibles, verificar_conflicto_atomic

def inicio(request):
    peluquerias = Peluqueria.objects.all()
    return render(request, 'salon/index.html', {'peluquerias': peluquerias})

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
        print(f"Error API: {e}")
        return JsonResponse({'horas': []})

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
                raise ValueError("Faltan datos")

            empleado = get_object_or_404(Empleado, id=empleado_id)
            fecha_naive = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
            try: inicio_cita = make_aware(fecha_naive) 
            except ValueError: inicio_cita = fecha_naive

            servicios_objs = Servicio.objects.filter(id__in=servicios_ids)
            duracion_total = sum([s.duracion for s in servicios_objs], timedelta())
            fin_cita = inicio_cita + duracion_total
            total_precio = sum([s.precio for s in servicios_objs])

            # ¿Tiene configurado Bold?
            usa_bold = bool(peluqueria.bold_api_key and peluqueria.bold_integrity_key)
            estado_inicial = 'P' if usa_bold else 'C'

            with transaction.atomic():
                if verificar_conflicto_atomic(empleado, inicio_cita, fin_cita):
                    return render(request, 'salon/agendar.html', {
                        'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados,
                        'error_mensaje': f"⚠️ Horario no disponible."
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
                # GUARDAMOS LOS SERVICIOS AQUÍ
                cita.servicios.set(servicios_objs)

            if usa_bold:
                # Flujo Bold: Calcular 50% y redirigir
                # 2. CORREGIDO: Usamos Decimal("0.5") para evitar el error con float
                monto_anticipo = int(total_precio * Decimal("0.5"))
                
                referencia = f"CITA-{cita.id}-{int(datetime.now().timestamp())}"
                cita.referencia_pago_bold = referencia
                cita.save()

                cadena_concatenada = f"{referencia}{monto_anticipo}COP{peluqueria.bold_integrity_key}"
                signature = hashlib.sha256(cadena_concatenada.encode('utf-8')).hexdigest()

                return render(request, 'salon/pago_bold.html', {
                    'cita': cita, 'monto_anticipo': monto_anticipo,
                    'signature': signature, 'peluqueria': peluqueria, 'referencia': referencia
                })

            else:
                # Flujo Normal: ¡NOTIFICAR AHORA! (Ya tiene servicios guardados)
                cita.enviar_notificacion_telegram()
                return redirect('cita_confirmada')
            
        except Exception as e:
            traceback.print_exc()
            return render(request, 'salon/agendar.html', {'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados, 'error_mensaje': str(e)})

    return render(request, 'salon/agendar.html', {
        'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados
    })

@csrf_exempt 
def retorno_bold(request):
    status = request.GET.get('tx_status')
    referencia = request.GET.get('reference')
    if not referencia: return redirect('inicio')

    try:
        cita = Cita.objects.get(referencia_pago_bold=referencia)
        if status == 'approved':
            cita.estado = 'C'
            # 3. CORREGIDO: También aquí usamos Decimal
            cita.abono_pagado = cita.precio_total * Decimal("0.5")
            cita.save()
            # Pago exitoso: Notificar Telegram ahora
            cita.enviar_notificacion_telegram()
            return redirect('cita_confirmada')
        elif status in ['rejected', 'failed']:
            cita.estado = 'A'
            cita.save()
            return HttpResponse("Pago rechazado. <a href='/'>Volver</a>")
        else:
            return HttpResponse("Pago pendiente...")
    except Cita.DoesNotExist:
        return redirect('inicio')

def cita_confirmada(request):
    return render(request, 'salon/confirmacion.html')

@login_required(login_url='/admin/login/')
def dashboard_dueño(request):
    try: peluqueria = request.user.perfil.peluqueria
    except: peluqueria = None
    if not peluqueria:
        if request.user.is_superuser: peluqueria = Peluqueria.objects.first()
        if not peluqueria: return render(request, 'salon/error_dashboard.html')

    hoy = now().date()
    citas_hoy = Cita.objects.filter(peluqueria=peluqueria, fecha_hora_inicio__date=hoy).count()
    ingresos_mes = Cita.objects.filter(peluqueria=peluqueria, fecha_hora_inicio__month=hoy.month, estado='C').aggregate(Sum('precio_total'))['precio_total__sum'] or 0
    proximas_citas = Cita.objects.filter(peluqueria=peluqueria, fecha_hora_inicio__gte=now(), estado='C').order_by('fecha_hora_inicio')[:5]

    context = {'peluqueria': peluqueria, 'citas_hoy': citas_hoy, 'ingresos_mes': ingresos_mes, 'proximas_citas': proximas_citas}
    return render(request, 'salon/dashboard.html', context)

def manifest_view(request):
    return JsonResponse({
        "name": "Citas Peluquería", "short_name": "Mi Salón", "start_url": "/", "display": "standalone",
        "background_color": "#ffffff", "theme_color": "#ec4899", "icons": []
    })
