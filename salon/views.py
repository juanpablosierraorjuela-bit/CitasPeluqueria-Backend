from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.db.models import Sum
from django.utils.timezone import make_aware, now
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta
import hashlib
import requests
from .models import Peluqueria, Servicio, Empleado, Cita, SolicitudSaaS
from .services import obtener_bloques_disponibles, verificar_conflicto_atomic

# =========================================================
# 👑 TUS CREDENCIALES DE SUPER ADMIN (PONLAS AQUÍ)
# =========================================================
ADMIN_TELEGRAM_TOKEN = "TU_TOKEN_DEL_BOT_AQUI"  # <--- PEGA TU TOKEN AQUÍ
ADMIN_CHAT_ID = "TU_CHAT_ID_AQUI"             # <--- PEGA TU ID AQUÍ

def enviar_alerta_admin(mensaje):
    """Envía alertas a tu Telegram personal"""
    if "TU_TOKEN" in ADMIN_TELEGRAM_TOKEN: return # Si no lo has puesto, no hace nada
    try:
        url = f"https://api.telegram.org/bot{ADMIN_TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": ADMIN_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"})
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

# ... (El resto de vistas: agendar_cita, retorno_bold, dashboard, etc. déjalas igual) ...
# Solo asegúrate de copiar las funciones de agendar y demás que ya tenías funcionales.
# Si necesitas el archivo COMPLETO de views con esto integrado, pídemelo y te lo pego entero.
