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
import requests
from .models import Peluqueria, Servicio, Empleado, Cita, SolicitudSaaS
from .services import obtener_bloques_disponibles, verificar_conflicto_atomic

# =========================================================
# 👑 TUS CREDENCIALES DE SUPER ADMIN
# =========================================================
ADMIN_TELEGRAM_TOKEN = "TU_TOKEN_DEL_BOT_AQUI"  # <--- ¡PON TU TOKEN AQUÍ!
ADMIN_CHAT_ID = "TU_CHAT_ID_AQUI"             # <--- ¡PON TU ID AQUÍ!

def enviar_alerta_admin(mensaje):
    """Envía alertas a tu Telegram personal"""
    if "TU_TOKEN" in ADMIN_TELEGRAM_TOKEN: return 
    try:
        url = f"https://api.telegram.org/bot{ADMIN_TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": ADMIN_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}, timeout=2)
    except: pass

def inicio(request):
    ciudad = request.GET.get('ciudad')
    ciudades = Peluqueria.objects.values_list('ciudad', flat=True).distinct().order_by('ciudad')
    peluquerias = Peluqueria.objects.all()
    if ciudad and ciudad != 'Todas': peluquerias = peluquerias.filter(ciudad__iexact=ciudad)
    return render(request, 'salon/index.html', {'peluquerias': peluquerias, 'ciudades': ciudades, 'ciudad_actual': ciudad})

def landing_saas(request):
    success = False
    if request.method == 'POST':
        try:
            nueva = SolicitudSaaS.objects.create(
                nombre_contacto=request.POST.get('nombre'),
                nombre_empresa=request.POST.get('empresa'),
                telefono=request.POST.get('telefono'),
                nicho=request.POST.get('nicho'),
                cantidad_empleados=request.POST.get('empleados')
            )
            success = True
            
            # ALERTA A TU CELULAR 🚨
            msg = f"🚀 *NUEVO CLIENTE INTERESADO*\n\n🏢 {nueva.nombre_empresa}\n👤 {nueva.nombre_contacto}\n📞 {nueva.telefono}"
            enviar_alerta_admin(msg)

        except Exception as e:
            print(f"Error: {e}")
    
    return render(request, 'salon/landing_saas.html', {'success': success})

def obtener_horas_disponibles(request):
    try:
        empleado_id = request.GET.get('empleado_id')
        fecha_str = request.GET.get('fecha')
        servicios_ids = request.GET.get('servicios_ids', '').split(',')
        if not (empleado_id and fecha_str and servicios_ids): return JsonResponse({'horas': []})

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
    except Exception:
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
            tipo_pago = request.POST.get('tipo_pago', 'completo') 

            if not (nombre and empleado_id and fecha_str and hora_str): raise ValueError("Faltan datos")

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
                    return render(request, 'salon/agendar.html', {'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados, 'error_mensaje': f"⚠️ Horario no disponible."})
                
                cita = Cita.objects.create(
                    peluqueria=peluqueria, cliente_nombre=nombre, cliente_telefono=telefono,
                    empleado=empleado, fecha_hora_inicio=inicio_cita, fecha_hora_fin=fin_cita,
                    precio_total=total_precio, estado=estado_inicial
                )
                cita.servicios.set(servicios_objs)

            if usa_bold:
                porcentaje = peluqueria.porcentaje_abono if peluqueria.porcentaje_abono > 0 else 50
                monto_anticipo = int(total_precio * porcentaje / 100) if tipo_pago == 'abono' else int(total_precio)
                
                cita.abono_pagado = monto_anticipo 
                referencia = f"CITA-{cita.id}-{int(datetime.now().timestamp())}"
                cita.referencia_pago_bold = referencia
                cita.save()

                cadena_concatenada = f"{referencia}{monto_anticipo}COP{peluqueria.bold_integrity_key}"
                signature = hashlib.sha256(cadena_concatenada.encode('utf-8')).hexdigest()

                return render(request, 'salon/pago_bold.html', {'cita': cita, 'monto_anticipo': monto_anticipo, 'signature': signature, 'peluqueria': peluqueria, 'referencia': referencia})
            else:
                cita.enviar_notificacion_telegram()
                enviar_alerta_admin(f"💰 *CITA AGENDADA EN {peluqueria.nombre}*\nTotal: ${total_precio}")
                return redirect('cita_confirmada')
            
        except Exception as e:
            traceback.print_exc()
            return render(request, 'salon/agendar.html', {'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados, 'error_mensaje': "Error técnico. Intente nuevamente."})

    return render(request, 'salon/agendar.html', {'peluqueria': peluqueria, 'servicios': servicios, 'empleados': empleados})

@csrf_exempt 
def retorno_bold(request):
    try:
        status = request.GET.get('bold-tx-status') or request.GET.get('tx_status')
        referencia = request.GET.get('bold-order-id') or request.GET.get('reference')
        if not referencia: return redirect('inicio')

        cita = Cita.objects.get(referencia_pago_bold=referencia)
        if cita.estado == 'C': return redirect('cita_confirmada')

        if status == 'approved':
            cita.estado = 'C'
            cita.save()
            cita.enviar_notificacion_telegram()
            enviar_alerta_admin(f"🤑 *PAGO BOLD EXITOSO*\nSalón: {cita.peluqueria.nombre}\nMonto: ${cita.abono_pagado}")
            return redirect('cita_confirmada')
        elif status in ['rejected', 'failed']:
            cita.estado = 'A'
            cita.save()
            return HttpResponse("<h1>Pago rechazado.</h1><a href='/'>Volver</a>")
    except Exception:
        return redirect('inicio')
    return redirect('inicio')

def cita_confirmada(request):
    return render(request, 'salon/confirmacion.html')

@login_required(login_url='/admin/login/')
def dashboard_dueño(request):
    peluqueria = None
    if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
        peluqueria = request.user.perfil.peluqueria
    elif request.user.is_superuser:
        peluqueria = Peluqueria.objects.first()
    
    if not peluqueria: return render(request, 'salon/error_dashboard.html')

    hoy = now().date()
    citas_hoy = Cita.objects.filter(peluqueria=peluqueria, fecha_hora_inicio__date=hoy).count()
    ingresos_mes = Cita.objects.filter(peluqueria=peluqueria, fecha_hora_inicio__month=hoy.month, estado='C').aggregate(Sum('precio_total'))['precio_total__sum'] or 0
    proximas_citas = Cita.objects.filter(peluqueria=peluqueria, fecha_hora_inicio__gte=now(), estado='C').order_by('fecha_hora_inicio')[:5]
    return render(request, 'salon/dashboard.html', {'peluqueria': peluqueria, 'citas_hoy': citas_hoy, 'ingresos_mes': ingresos_mes, 'proximas_citas': proximas_citas})

def manifest_view(request):
    # ICONOS: Aquí "engañamos" al navegador diciendo que existen estos iconos.
    # IMPORTANTE: Asegúrate de subir una imagen (tu logo) llamada 'icon-512.png' a la carpeta static/img/
    icons = [
        {"src": "/static/img/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/static/img/icon-512.png", "sizes": "512x512", "type": "image/png"}
    ]
    
    return JsonResponse({
        "name": "Citas App",
        "short_name": "Citas",
        "start_url": "/", 
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#ec4899",
        "icons": icons
    })
