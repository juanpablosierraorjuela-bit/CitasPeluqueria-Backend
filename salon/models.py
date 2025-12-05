import requests
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.utils.text import slugify
from datetime import timedelta, datetime

# =============================================================
# 0. FUNCIONES REUTILIZABLES
# =============================================================

def enviar_mensaje_telegram(token, chat_id, mensaje):
    """Función central para enviar cualquier mensaje a Telegram."""
    if not token or not chat_id:
        return False, "Token o Chat ID no configurados."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, data=data, timeout=5)
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get('ok'):
            return True, "Mensaje enviado con éxito."
        else:
            error_msg = response_data.get('description', 'Error desconocido de la API.')
            return False, f"Error de la API: {error_msg}"

    except requests.exceptions.RequestException as e:
        return False, f"Error de conexión de red: {e}"


# =============================================================
# 1. MODELOS BASE (El resto del código de modelos queda igual)
# =============================================================

class Peluqueria(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True, null=True) 
    nombre_visible = models.CharField(max_length=100, default="Mi Salón")
    
    # --- CONFIGURACIÓN TELEGRAM AUTÓNOMA ---
    telegram_token = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="Token del bot (ej: 123456:ABC-DEF)"
    )
    telegram_chat_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="ID de chat del dueño/grupo (ej: -123456789)"
    )
    
    # ... (el resto del modelo Peluqueria y los demás modelos: Servicio, Empleado, HorarioSemanal, Cita, PerfilUsuario) ...

# -------------------
# NOTA: Debes asegurar que el resto de tus modelos (Servicio, Empleado, Cita, PerfilUsuario) 
# y la señal crear_perfil() estén debajo de esta línea.
# -------------------

# =============================================================
# 5. SEÑALES (Actualizadas para usar la función central)
# =============================================================

# ... (Señal crear_perfil, crear_horario_por_defecto, etc.) ...

@receiver(m2m_changed, sender=Cita.servicios)
def notificar_nueva_cita(sender, instance, action, **kwargs):
    if action == 'post_add': 
        peluqueria = instance.peluqueria
        token = peluqueria.telegram_token
        chat_id = peluqueria.telegram_chat_id
        
        if token and chat_id:
            servicios_nombres = ", ".join([s.nombre for s in instance.servicios.all()])
            
            mensaje = (
                f"💈 *NUEVA CITA EN {peluqueria.nombre_visible.upper()}*\n\n"
                f"👤 *Cliente:* {instance.cliente_nombre}\n"
                f"✂️ *Estilista:* {instance.empleado.nombre}\n"
                f"📅 *Fecha:* {instance.fecha_hora_inicio.strftime('%d/%m/%Y %H:%M')}"
            )
            
            # Llamamos a la función central
            exito, mensaje_resultado = enviar_mensaje_telegram(token, chat_id, mensaje)
            
            if not exito:
                print(f"❌ FALLO DE NOTIFICACIÓN: {mensaje_resultado}")