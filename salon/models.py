# UBICACIÓN: salon/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify
from django.utils import timezone
import pytz 

class ConfiguracionPlataforma(models.Model):
    solo_un_registro = models.CharField(max_length=1, default='X', editable=False)
    
    # CAMPO NUEVO: TU LINK DE BOLD (Estático)
    link_pago_bold = models.URLField(
        "Link de Pago Bold", 
        default="https://checkout.bold.co/payment/LNK_QZ5NWWY82P", 
        help_text="Pega aquí el Link de Pago Único de Bold."
    )
    
    # Telegram
    telegram_token = models.CharField(max_length=255, blank=True)
    telegram_chat_id = models.CharField(max_length=255, blank=True)
    precio_mensualidad = models.IntegerField(default=130000)

    # (Las llaves viejas se eliminan para no confundir)

    class Meta:
        verbose_name = "Configuración Dueño PASO"
        verbose_name_plural = "Configuración Dueño PASO"

    def __str__(self): return "Configuración de Pagos"

# --- MODELOS BASE ---
class Peluqueria(models.Model):
    nombre = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    nombre_visible = models.CharField(max_length=200, default="Mi Salón")
    ciudad = models.CharField(max_length=100, default="Tunja")
    direccion = models.CharField(max_length=200, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    codigo_pais_wa = models.CharField(max_length=5, default="57")
    latitud = models.FloatField(default=5.5353)
    longitud = models.FloatField(default=-73.3678)
    hora_apertura = models.TimeField(default="08:00")
    hora_cierre = models.TimeField(default="20:00")
    porcentaje_abono = models.IntegerField(default=50)
    
    # Datos Suscripción
    fecha_inicio_contrato = models.DateTimeField(default=timezone.now)
    activo_saas = models.BooleanField(default=True)

    # Integraciones del Cliente (Peluquería) - Estas SÍ se quedan
    telegram_token = models.CharField(max_length=200, blank=True, null=True)
    telegram_chat_id = models.CharField(max_length=100, blank=True, null=True)
    bold_api_key = models.CharField(max_length=255, blank=True, null=True)
    bold_integrity_key = models.CharField(max_length=255, blank=True, null=True)
    bold_secret_key = models.CharField(max_length=255, blank=True, null=True)
    
    @property
    def esta_abierto(self):
        try: return self.hora_apertura <= timezone.now().astimezone(pytz.timezone('America/Bogota')).time() <= self.hora_cierre
        except: return True

    def save(self, *args, **kwargs):
        if not self.slug: self.slug = slugify(self.nombre)
        if self.ciudad: self.ciudad = self.ciudad.title().strip()
        super().save(*args, **kwargs)
    def __str__(self): return self.nombre_visible

class Cupon(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='cupones')
    codigo = models.CharField(max_length=50)
    porcentaje_descuento = models.IntegerField(default=10)
    activo = models.BooleanField(default=True)
    usos_restantes = models.IntegerField(default=100)

class Servicio(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='servicios')
    nombre = models.CharField(max_length=100)
    duracion = models.DurationField()
    precio = models.IntegerField()
    @property
    def str_duracion(self):
        ts = int(self.duracion.total_seconds())
        return f"{ts//3600}h {(ts%3600)//60}m" if ts//3600 > 0 else f"{(ts%3600)//60} min"
    def __str__(self): return f"{self.nombre} - ${self.precio}"

class Empleado(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='empleados')
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='empleado_perfil')
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    email_contacto = models.EmailField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    def __str__(self): return f"{self.nombre} {self.apellido}"

class HorarioEmpleado(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='horarios')
    dia_semana = models.IntegerField(choices=((0,'L'),(1,'M'),(2,'X'),(3,'J'),(4,'V'),(5,'S'),(6,'D')))
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    almuerzo_inicio = models.TimeField(blank=True, null=True)
    almuerzo_fin = models.TimeField(blank=True, null=True)
    class Meta: unique_together = ('empleado', 'dia_semana')

class Ausencia(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    motivo = models.CharField(max_length=200, blank=True)

class Cita(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='citas')
    cliente_nombre = models.CharField(max_length=150)
    cliente_telefono = models.CharField(max_length=20)
    servicios = models.ManyToManyField(Servicio)
    precio_total = models.IntegerField(default=0)
    descuento_aplicado = models.IntegerField(default=0)
    abono_pagado = models.IntegerField(default=0)
    referencia_pago_bold = models.CharField(max_length=100, blank=True, null=True)
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    fecha_hora_inicio = models.DateTimeField()
    fecha_hora_fin = models.DateTimeField()
    creado_en = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=1, choices=[('P', 'Pendiente'), ('C', 'Confirmada'), ('X', 'Cancelada')], default='C')
    
    def enviar_notificacion_telegram(self):
        try:
            if self.peluqueria.telegram_token and self.peluqueria.telegram_chat_id:
                msg = f"🔥 *NUEVA CITA*\nCliente: {self.cliente_nombre}\nTotal: ${self.precio_total}"
                requests.post(f"https://api.telegram.org/bot{self.peluqueria.telegram_token}/sendMessage", data={"chat_id": self.peluqueria.telegram_chat_id, "text": msg, "parse_mode": "Markdown"})
        except: pass

class PerfilUsuario(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.SET_NULL, null=True, blank=True)
    es_dueño = models.BooleanField(default=False)

class SolicitudSaaS(models.Model):
    nombre_contacto = models.CharField(max_length=100)
    nombre_empresa = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20)
    nichos = models.CharField(max_length=50)
    cantidad_empleados = models.CharField(max_length=50)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    atendido = models.BooleanField(default=False)

@receiver(post_save, sender=User)
def crear_perfil(sender, instance, created, **kwargs):
    if created: PerfilUsuario.objects.get_or_create(user=instance)
