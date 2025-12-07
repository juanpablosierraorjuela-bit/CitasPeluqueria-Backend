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
    
    # TELEGRAM
    telegram_token = models.CharField(max_length=100, blank=True, null=True)
    telegram_chat_id = models.CharField(max_length=100, blank=True, null=True)
    
    # DATOS DE CONTACTO
    direccion = models.CharField(max_length=200, blank=True, null=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    hora_apertura = models.TimeField(default="08:00")
    hora_cierre = models.TimeField(default="20:00")

    # --- BOLD (PASARELA DE PAGO) ---
    bold_api_key = models.CharField(max_length=200, blank=True, null=True, help_text="Llave pública de Bold (PK-...)")
    bold_integrity_key = models.CharField(max_length=200, blank=True, null=True, help_text="Llave de integridad para firmar transacciones")
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre_visible

class Servicio(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='servicios')
    nombre = models.CharField(max_length=100)
    duracion = models.DurationField(default=timedelta(minutes=30), help_text="Formato HH:MM:SS (Ej: 00:30:00 para 30 min)") 
    precio = models.DecimalField(max_digits=8, decimal_places=2) 
    descripcion = models.TextField(blank=True, null=True)

    @property
    def str_duracion(self):
        """Muestra la duración amigable (ej: 30 min)"""
        total_seconds = int(self.duracion.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
        return f"{minutes} min"

    def __str__(self):
        return f"{self.nombre} - ${self.precio:,.0f}"

# =============================================================
# 2. EMPLEADOS Y HORARIOS
# =============================================================

class Empleado(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='empleados')
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    servicios_que_realiza = models.ManyToManyField(Servicio)
    
    def __str__(self):
        return f"{self.nombre} {self.apellido}"

DIAS_SEMANA = ((0,'Lunes'),(1,'Martes'),(2,'Miércoles'),(3,'Jueves'),(4,'Viernes'),(5,'Sábado'),(6,'Domingo'))

class HorarioSemanal(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, blank=True, null=True)
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='horarios')
    dia_semana = models.IntegerField(choices=DIAS_SEMANA)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    descanso_inicio = models.TimeField(blank=True, null=True)
    descanso_fin = models.TimeField(blank=True, null=True)
    
    class Meta: 
        unique_together = ('empleado', 'dia_semana') 

    def save(self, *args, **kwargs):
        if not self.peluqueria_id and self.empleado: 
            self.peluqueria = self.empleado.peluqueria
        super().save(*args, **kwargs)

class Ausencia(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='ausencias')
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    motivo = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return f"Ausencia {self.empleado} ({self.fecha_inicio} - {self.fecha_fin})"

# =============================================================
# 3. CITA Y PERFIL
# =============================================================

class Cita(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE)
    cliente_nombre = models.CharField(max_length=100)
    cliente_telefono = models.CharField(max_length=20)
    servicios = models.ManyToManyField(Servicio) 
    precio_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # PAGOS BOLD
    abono_pagado = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    referencia_pago_bold = models.CharField(max_length=100, blank=True, null=True)

    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    fecha_hora_inicio = models.DateTimeField()
    fecha_hora_fin = models.DateTimeField() 
    
    # Estados: P=Pendiente Pago, C=Confirmada, A=Anulada
    estado = models.CharField(max_length=1, choices=[('P','Pendiente Pago'),('C','Confirmada'),('A','Anulada')], default='P')

    def __str__(self):
        return f"Cita {self.cliente_nombre}"
    
    def enviar_notificacion_telegram(self):
        """
        Envía el mensaje a Telegram MANUALMENTE.
        Esto asegura que los servicios SÍ aparezcan en el mensaje.
        """
        try:
            token = self.peluqueria.telegram_token
            chat_id = self.peluqueria.telegram_chat_id
            
            if not token or not chat_id: return

            # Construir lista de servicios bonita
            lista_servicios = ""
            for s in self.servicios.all():
                lista_servicios += f"• {s.nombre} ({s.str_duracion})\n"
            
            if not lista_servicios:
                lista_servicios = "(Sin servicios especificados)"

            mensaje = (
                f"🔔 *NUEVA CITA CONFIRMADA*\n\n"
                f"👤 *Cliente:* {self.cliente_nombre}\n"
                f"📞 *Tel:* {self.cliente_telefono}\n"
                f"📅 *Fecha:* {self.fecha_hora_inicio.strftime('%d/%m/%Y')}\n"
                f"⏰ *Hora:* {self.fecha_hora_inicio.strftime('%H:%M')}\n"
                f"💇 *Estilista:* {self.empleado.nombre}\n\n"
                f"📋 *Servicios:*\n{lista_servicios}\n"
                f"💰 *Total:* ${self.precio_total:,.0f}\n"
                f"💳 *Abono:* ${self.abono_pagado:,.0f}"
            )

            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, data={"chat_id": chat_id, "text": mensaje, "parse_mode": "Markdown"}, timeout=3)
        except Exception as e:
            print(f"❌ Error Telegram Manual: {e}")

class PerfilUsuario(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.SET_NULL, null=True, blank=True)

@receiver(post_save, sender=User)
def crear_perfil(sender, instance, created, **kwargs):
    if created: PerfilUsuario.objects.create(user=instance)

# NOTA: NO HAY SEÑAL AUTOMÁTICA DE CITA AQUÍ. SE LLAMA EN LAS VISTAS.
