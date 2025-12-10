from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify
from datetime import timedelta
from django.utils import timezone
import requests

# =============================================================
# 1. MODELOS BASE
# =============================================================

class Peluqueria(models.Model):
    nombre = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, help_text="Identificador único en la URL (ej: mi-salon)") 
    nombre_visible = models.CharField(max_length=200, default="Mi Salón")
    ciudad = models.CharField(max_length=100, default="Tunja")
    
    # DATOS DE CONTACTO
    direccion = models.CharField(max_length=200, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    
    # IMPORTANTE: Nuevo campo para el código de país de WhatsApp (internacionalización)
    codigo_pais_wa = models.CharField(max_length=5, default="57", help_text="Código de país para WhatsApp (Ej: 57 para Colombia)")
    
    # CONFIGURACIÓN DEL NEGOCIO
    porcentaje_abono = models.IntegerField(default=50)
    
    # INTEGRACIÓN TELEGRAM
    telegram_token = models.CharField(max_length=200, blank=True, null=True)
    telegram_chat_id = models.CharField(max_length=100, blank=True, null=True)
    
    # INTEGRACIÓN BOLD
    bold_api_key = models.CharField(max_length=200, blank=True, null=True)
    bold_integrity_key = models.CharField(max_length=200, blank=True, null=True)
    
    def save(self, *args, **kwargs):
        if not self.slug: self.slug = slugify(self.nombre)
        if self.ciudad: self.ciudad = self.ciudad.title().strip()
        super().save(*args, **kwargs)

    def __str__(self): return f"{self.nombre_visible} ({self.ciudad})"

class Servicio(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='servicios')
    nombre = models.CharField(max_length=100)
    duracion = models.DurationField() 
    precio = models.IntegerField()
    # 'descripcion' FUE ELIMINADO EN MIGRACIÓN 0006

    @property
    def str_duracion(self):
        total_seconds = int(self.duracion.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if hours > 0: return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
        return f"{minutes} min"

    def __str__(self): return f"{self.nombre} - ${self.precio:,.0f}"

# =============================================================
# 2. EMPLEADOS Y CITA
# =============================================================

class Empleado(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='empleados')
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='empleado_perfil')
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    email_contacto = models.EmailField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    # 'servicios_que_realiza' FUE ELIMINADO EN MIGRACIÓN 0006

    def __str__(self): return f"{self.nombre} {self.apellido}"

DIAS_SEMANA = ((0,'Lunes'),(1,'Martes'),(2,'Miércoles'),(3,'Jueves'),(4,'Viernes'),(5,'Sábado'),(6,'Domingo'))

class HorarioEmpleado(models.Model):
    # Reemplaza a HorarioSemanal desde la migración 0006
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='horarios')
    dia_semana = models.IntegerField(choices=DIAS_SEMANA)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    almuerzo_inicio = models.TimeField(blank=True, null=True, help_text="Inicio del descanso")
    almuerzo_fin = models.TimeField(blank=True, null=True, help_text="Fin del descanso")

    class Meta: 
        unique_together = ('empleado', 'dia_semana') 
        ordering = ['dia_semana', 'hora_inicio']

class Ausencia(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    motivo = models.CharField(max_length=200, blank=True)
    def __str__(self): return f"Ausencia {self.empleado}"

class Cita(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='citas')
    cliente_nombre = models.CharField(max_length=150)
    cliente_telefono = models.CharField(max_length=20)
    servicios = models.ManyToManyField(Servicio) 
    precio_total = models.IntegerField(default=0)
    abono_pagado = models.IntegerField(default=0)
    referencia_pago_bold = models.CharField(max_length=100, blank=True, null=True)
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    fecha_hora_inicio = models.DateTimeField()
    fecha_hora_fin = models.DateTimeField() 
    creado_en = models.DateTimeField(auto_now_add=True) # Faltaba este campo vital
    estado = models.CharField(max_length=1, choices=[('P','Pendiente Pago'),('C','Confirmada'),('A','Anulada')], default='C')

    def __str__(self): return f"Cita {self.cliente_nombre}"
    
    def enviar_notificacion_telegram(self):
        try:
            token = self.peluqueria.telegram_token
            chat_id = self.peluqueria.telegram_chat_id
            
            if token and chat_id:
                total = self.precio_total
                abono = self.abono_pagado
                pendiente = total - abono
                
                lista_servicios = ""
                for s in self.servicios.all():
                    lista_servicios += f"✂️ {s.nombre}\n"
                
                # USO DEL NUEVO CAMPO: código de país configurable
                codigo_pais = self.peluqueria.codigo_pais_wa
                link_wa = f"https://wa.me/{codigo_pais}{self.cliente_telefono.replace(' ', '')}"

                msg = (
                    f"🔥 *NUEVA RESERVA CONFIRMADA*\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"👤 *Cliente:* {self.cliente_nombre}\n"
                    f"📱 *Tel:* [{self.cliente_telefono}]({link_wa}) 👈(Clic para chatear)\n\n"
                    f"📅 *Fecha:* {self.fecha_hora_inicio.strftime('%d/%m/%Y')}\n"
                    f"⏰ *Hora:* {self.fecha_hora_inicio.strftime('%I:%M %p')}\n"
                    f"💈 *Estilista:* {self.empleado.nombre}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📝 *SERVICIOS:*\n{lista_servicios}\n"
                    f"💰 *FINANZAS:*\n"
                    f"• Total: ${total:,.0f}\n"
                    f"• Pagado App: ${abono:,.0f}\n"
                    f"• 🚨 *COBRAR EN LOCAL: ${pendiente:,.0f}* 🚨"
                )

                requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage", 
                    data={
                        "chat_id": chat_id, 
                        "text": msg, 
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": True
                    },
                    timeout=5
                )
        except Exception as e:
            print(f"Error enviando Telegram: {e}")

class PerfilUsuario(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, null=True, blank=True)
    es_dueño = models.BooleanField(default=False)

@receiver(post_save, sender=User)
def crear_perfil(sender, instance, created, **kwargs):
    if created: PerfilUsuario.objects.create(user=instance)

# =============================================================
# 3. SOLICITUDES SAAS (LEADS)
# =============================================================

class SolicitudSaaS(models.Model):
    nombre_contacto = models.CharField(max_length=100)
    nombre_empresa = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20)
    nicho = models.CharField(max_length=50)
    cantidad_empleados = models.CharField(max_length=50)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    atendido = models.BooleanField(default=False)

    def __str__(self): return f"Lead: {self.nombre_empresa}"
    class Meta: verbose_name_plural = "Solicitudes SaaS"
