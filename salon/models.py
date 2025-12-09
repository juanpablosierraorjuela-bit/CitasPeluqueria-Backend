from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import uuid

class Peluqueria(models.Model):
    nombre = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, help_text="Identificador único en la URL (ej: mi-salon)")
    nombre_visible = models.CharField(max_length=200, default="Mi Salón")
    ciudad = models.CharField(max_length=100, default="Tunja")
    direccion = models.CharField(max_length=200, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    
    # Configuración de Pagos (Bold)
    bold_api_key = models.CharField(max_length=200, blank=True, null=True)
    bold_integrity_key = models.CharField(max_length=200, blank=True, null=True)
    porcentaje_abono = models.IntegerField(default=50, help_text="Porcentaje que debe pagar el cliente para reservar")
    
    # Configuración de Notificaciones
    telegram_token = models.CharField(max_length=200, blank=True, null=True)
    telegram_chat_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self): return self.nombre

class PerfilUsuario(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, null=True, blank=True)
    es_dueño = models.BooleanField(default=False)

    def __str__(self): return f"Perfil de {self.user.username}"

class Servicio(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='servicios')
    nombre = models.CharField(max_length=100)
    duracion = models.DurationField(help_text="Ej: 00:30:00 para 30 min")
    precio = models.IntegerField()

    def __str__(self): return f"{self.nombre} (${self.precio})"
    
    @property
    def str_duracion(self):
        total_seconds = int(self.duracion.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if hours > 0: return f"{hours}h {minutes}min"
        return f"{minutes} min"

class Empleado(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='empleados')
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    def __str__(self): return f"{self.nombre} {self.apellido}"

# --- NUEVO: MODELO PARA QUE CONTROLEN SUS HORARIOS ---
class HorarioEmpleado(models.Model):
    DIAS = [
        (0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'), 
        (3, 'Jueves'), (4, 'Viernes'), (5, 'Sábado'), (6, 'Domingo')
    ]
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='horarios')
    dia_semana = models.IntegerField(choices=DIAS)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    
    class Meta:
        ordering = ['dia_semana', 'hora_inicio']
        verbose_name = "Horario de Trabajo"
        verbose_name_plural = "Horarios de Trabajo"

    def __str__(self): return f"{self.get_dia_semana_display()}: {self.hora_inicio} - {self.hora_fin}"

class Cita(models.Model):
    ESTADOS = [('P', 'Pendiente Pago'), ('C', 'Confirmada'), ('A', 'Anulada/Fallida')]
    
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='citas')
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    servicios = models.ManyToManyField(Servicio)
    
    cliente_nombre = models.CharField(max_length=150)
    cliente_telefono = models.CharField(max_length=20)
    
    fecha_hora_inicio = models.DateTimeField()
    fecha_hora_fin = models.DateTimeField()
    
    precio_total = models.IntegerField(default=0)
    abono_pagado = models.IntegerField(default=0)
    referencia_pago_bold = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(max_length=1, choices=ESTADOS, default='C')
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self): return f"{self.cliente_nombre} - {self.fecha_hora_inicio}"

    def enviar_notificacion_telegram(self):
        # Lógica para enviar aviso al Telegram del dueño
        if self.peluqueria.telegram_token and self.peluqueria.telegram_chat_id:
            import requests
            msg = f"📅 *NUEVA CITA CONFIRMADA*\n👤 {self.cliente_nombre}\n📱 {self.cliente_telefono}\n💇 {self.empleado.nombre}\n🕒 {self.fecha_hora_inicio.strftime('%d/%m %I:%M %p')}\n💰 Total: ${self.precio_total}"
            try:
                requests.post(f"https://api.telegram.org/bot{self.peluqueria.telegram_token}/sendMessage", 
                              data={"chat_id": self.peluqueria.telegram_chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=1)
            except: pass

class Ausencia(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    motivo = models.CharField(max_length=200, blank=True)

class SolicitudSaaS(models.Model):
    nombre_contacto = models.CharField(max_length=100)
    nombre_empresa = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20)
    nicho = models.CharField(max_length=50)
    cantidad_empleados = models.CharField(max_length=50)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    atendido = models.BooleanField(default=False)
