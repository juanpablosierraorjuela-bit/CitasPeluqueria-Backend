from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.db.models import Sum
from django.utils.timezone import make_aware, now
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import traceback
import json  # Importamos json para mostrar los datos bonitos

from .models import Peluqueria, Servicio, Empleado, Cita
from .services import obtener_bloques_disponibles, verificar_conflicto_atomic

# 1. VISTA DE INICIO
def inicio(request):
    ciudad_seleccionada = request.GET.get('ciudad')
    ciudades_disponibles = Peluqueria.objects.values_list('ciudad', flat=True).distinct().order_by('ciudad')
    peluquerias = Peluqueria.objects.all()
    
    if ciudad_seleccionada and ciudad_seleccionada != 'Todas':
        peluquerias = peluquerias.filter(ciudad__iexact=ciudad_seleccionada)
        
    context = {
        'peluquerias': peluquerias,
        'ciudades': ciudades_disponibles,
        'ciudad_actual': ciudad_seleccionada
    }
    return render(request, 'salon/index.html', context)

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

# 3. AGENDAR CITA
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
            
            tipo_pago = request.POST.get('tipo_pago', 'completo') 

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
                cita.servicios.set(servicios_objs)

            if usa_bold:
                if tipo_pago == 'mitad':
                    monto_anticipo = int(total_precio / 2)
                else:
                    monto_anticipo = int(total_precio)
                
                cita.abono_pagado = monto_anticipo 
                
                referencia = f"CITA-{cita.id}-{int(datetime.now().timestamp())}"
                cita.referencia_pago_bold = referencia
                cita.save()

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
                cita.enviar_notificacion_telegram()
                return redirect('cita_confirmada')
            
        except Exception as e:
            traceback.print_exc()
            return render(request, 'salon/agendar.html', {'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados, 'error_mensaje': f"Error técnico: {str(e)}"})

    return render(request, 'salon/agendar.html', {
        'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados
    })

# 4. RESPUESTA DE BOLD (MODO DIAGNÓSTICO)
@csrf_exempt 
def retorno_bold(request):
    # Capturamos TODOS los datos que llegan
    datos_recibidos = request.GET.dict()
    
    # Intentamos buscar la referencia
    referencia = datos_recibidos.get('orderId') or datos_recibidos.get('reference') or datos_recibidos.get('bold_order_id')
    status = datos_recibidos.get('tx_status') or datos_recibidos.get('transactionStatus')

    # --- SI NO ENCUENTRA LA REFERENCIA, MOSTRAMOS PANTALLA DE ERROR CON DATOS ---
    if not referencia:
        return HttpResponse(f"""
            <div style='font-family:sans-serif; padding:20px; text-align:center;'>
                <h1 style='color:red;'>⚠️ DIAGNÓSTICO: DATOS NO ENCONTRADOS</h1>
                <p>Bold regresó, pero no veo el ID de la orden.</p>
                <hr>
                <h3>Esto es lo que llegó exactamente:</h3>
                <pre style='background:#f0f0f0; padding:15px; text-align:left;'>{json.dumps(datos_recibidos, indent=4)}</pre>
                <hr>
                <a href='/'>Volver al Inicio</a>
            </div>
        """)

    try:
        cita = Cita.objects.get(referencia_pago_bold=referencia)
        
        # SI TODO SALE BIEN, MOSTRAMOS PANTALLA DE ÉXITO MANUAL
        if status == 'approved':
            cita.estado = 'C'
            cita.save()
            cita.enviar_notificacion_telegram()
            return redirect('cita_confirmada') # <--- Si funciona, esto te llevará a la confirmación
            
        elif status in ['rejected', 'failed']:
            cita.estado = 'A'
            cita.save()
            return HttpResponse(f"<h1 style='color:red'>PAGO RECHAZADO (Estado: {status})</h1><a href='/'>Volver</a>")
        else:
            return HttpResponse(f"<h1>Estado desconocido: {status}</h1>")

    except Cita.DoesNotExist:
        return HttpResponse(f"""
            <h1 style='color:red'>ERROR: Cita No Encontrada</h1>
            <p>Recibí la referencia: <b>{referencia}</b>, pero no existe en la base de datos.</p>
        """)

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
