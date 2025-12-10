from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify
from datetime import timedelta
import requests

# =============================================================
# 1. MODELOS BASE
# =============================================================

class Peluqueria(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True, null=True) 
    nombre_visible = models.CharField(max_length=100, default="Mi Salón")
    ciudad = models.CharField(max_length=100, default="Tunja", help_text="Ciudad para filtrar en la App Global")
    
    # DATOS DE CONTACTO
    direccion = models.CharField(max_length=200, blank=True, null=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    
    # CONFIGURACIÓN DEL NEGOCIO
    porcentaje_abono = models.IntegerField(default=50, help_text="Porcentaje de abono (Ej: 50).")
    
    # INTEGRACIÓN TELEGRAM
    telegram_token = models.CharField(max_length=100, blank=True, null=True)
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
    duracion = models.DurationField(default=timedelta(minutes=30)) 
    precio = models.DecimalField(max_digits=8, decimal_places=2) 
    descripcion = models.TextField(blank=True, null=True)

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
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    servicios_que_realiza = models.ManyToManyField(Servicio)
    def __str__(self): return f"{self.nombre} {self.apellido}"

DIAS_SEMANA = ((0,'Lunes'),(1,'Martes'),(2,'Miércoles'),(3,'Jueves'),(4,'Viernes'),(5,'Sábado'),(6,'Domingo'))

class HorarioSemanal(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, blank=True, null=True)
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='horarios')
    dia_semana = models.IntegerField(choices=DIAS_SEMANA)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    descanso_inicio = models.TimeField(blank=True, null=True)
    descanso_fin = models.TimeField(blank=True, null=True)
    class Meta: unique_together = ('empleado', 'dia_semana') 
    def save(self, *args, **kwargs):
        if not self.peluqueria_id and self.empleado: self.peluqueria = self.empleado.peluqueria
        super().save(*args, **kwargs)

class Ausencia(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='ausencias')
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    motivo = models.CharField(max_length=200, blank=True, null=True)
    def __str__(self): return f"Ausencia {self.empleado}"

class Cita(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE)
    cliente_nombre = models.CharField(max_length=100)
    cliente_telefono = models.CharField(max_length=20)
    servicios = models.ManyToManyField(Servicio) 
    precio_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    abono_pagado = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    referencia_pago_bold = models.CharField(max_length=100, blank=True, null=True)
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    fecha_hora_inicio = models.DateTimeField()
    fecha_hora_fin = models.DateTimeField() 
    estado = models.CharField(max_length=1, choices=[('P','Pendiente Pago'),('C','Confirmada'),('A','Anulada')], default='P')

    def __str__(self): return f"Cita {self.cliente_nombre}"
    
    # --- MÉTODO MEJORADO DE NOTIFICACIÓN ---
    def enviar_notificacion_telegram(self):
        try:
            token = self.peluqueria.telegram_token
            chat_id = self.peluqueria.telegram_chat_id
            
            if token and chat_id:
                # 1. Calcular saldos
                total = self.precio_total
                abono = self.abono_pagado
                pendiente = total - abono
                
                # 2. Formatear lista de servicios
                lista_servicios = ""
                for s in self.servicios.all():
                    lista_servicios += f"✂️ {s.nombre}\n"
                
                # 3. Crear enlace directo a WhatsApp (Asumiendo +57 Colombia)
                link_wa = f"https://wa.me/57{self.cliente_telefono.replace(' ', '')}"

                # 4. Construir el MENSAJE NIVEL SUPERIOR
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

                # 5. Enviar
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
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.SET_NULL, null=True, blank=True)

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
    nicho = models.CharField(max_length=20)
    cantidad_empleados = models.CharField(max_length=20)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    atendido = models.BooleanField(default=False)

    def __str__(self): return f"Lead: {self.nombre_empresa}"
    class Meta: verbose_name_plural = "Solicitudes SaaS"
