# UBICACIÓN: salon/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify
from django.utils import timezone
import requests
import pytz 

# =============================================================
# 1. CONFIGURACIÓN GLOBAL (TU PAGO COMO DUEÑO)
# =============================================================
class ConfiguracionPlataforma(models.Model):
    solo_un_registro = models.CharField(max_length=1, default='X', editable=False)
    
    # Link de respaldo por si falla la API
    link_pago_bold = models.URLField(
        "Link de Pago Bold (Respaldo)", 
        default="https://checkout.bold.co/payment/LNK_QZ5NWWY82P"
    )
    
    # Tus credenciales para cobrar la mensualidad (SaaS)
    bold_secret_key = models.CharField(max_length=255, blank=True, null=True, help_text="Tu llave secreta de Bold para generar cobros")
    
    telegram_token = models.CharField(max_length=255, blank=True)
    telegram_chat_id = models.CharField(max_length=255, blank=True)
    precio_mensualidad = models.IntegerField(default=130000)

    class Meta:
        verbose_name = "Configuración Dueño PASO"
        verbose_name_plural = "Configuración Dueño PASO"

    def __str__(self): return "Configuración de Pagos"

# =============================================================
# 2. MODELOS BASE
# =============================================================

class Peluqueria(models.Model):
    nombre = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    nombre_visible = models.CharField(max_length=200, default="Mi Salón")
    ciudad = models.CharField(max_length=100, default="Tunja")
    direccion = models.CharField(max_length=200, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    codigo_pais_wa = models.CharField(max_length=5, default="57")
    
    # Configuración de Pagos del Negocio
    porcentaje_abono = models.IntegerField(default=50)
    
    # BOLD (Integración API)
    bold_api_key = models.CharField(max_length=255, blank=True, null=True)
    bold_integrity_key = models.CharField(max_length=255, blank=True, null=True)
    bold_secret_key = models.CharField(max_length=255, blank=True, null=True)
    
    # NEQUI (Integración Manual/Visual)
    nequi_celular = models.CharField(max_length=20, blank=True, null=True, help_text="Número Nequi para transferencias")
    nequi_qr_imagen = models.ImageField(upload_to='qrs_nequi/', blank=True, null=True, help_text="Sube el QR de Nequi")

    # DATOS DE SUSCRIPCIÓN
    fecha_inicio_contrato = models.DateTimeField(default=timezone.now)
    activo_saas = models.BooleanField(default=True)

    # Integraciones
    telegram_token = models.CharField(max_length=200, blank=True, null=True)
    telegram_chat_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Horarios Generales
    hora_apertura = models.TimeField(default="08:00")
    hora_cierre = models.TimeField(default="20:00")
    latitud = models.FloatField(default=5.5353)
    longitud = models.FloatField(default=-73.3678)

    @property
    def acepta_pagos_digitales(self):
        # Verifica si tiene configurado Bold O Nequi
        return bool(self.bold_api_key) or bool(self.nequi_celular)

    def save(self, *args, **kwargs):
        if not self.slug: self.slug = slugify(self.nombre)
        if self.ciudad: self.ciudad = self.ciudad.title().strip()
        super().save(*args, **kwargs)

    def __str__(self): return self.nombre_visible

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

DIAS = ((0,'L'),(1,'M'),(2,'X'),(3,'J'),(4,'V'),(5,'S'),(6,'D'))
class HorarioEmpleado(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='horarios')
    dia_semana = models.IntegerField(choices=DIAS)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    almuerzo_inicio = models.TimeField(blank=True, null=True)
    almuerzo_fin = models.TimeField(blank=True, null=True)
    class Meta: unique_together = ('empleado', 'dia_semana')

class Ausencia(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='ausencias')
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    motivo = models.CharField(max_length=200, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

class Cita(models.Model):
    ESTADOS = [('P', 'Pendiente'), ('C', 'Confirmada'), ('X', 'Cancelada')]
    METODOS_PAGO = [('BOLD', 'Bold'), ('NEQUI', 'Nequi'), ('SITIO', 'En Sitio')]
    
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='citas')
    cliente_nombre = models.CharField(max_length=150)
    cliente_telefono = models.CharField(max_length=20)
    servicios = models.ManyToManyField(Servicio)
    
    precio_total = models.IntegerField(default=0)
    descuento_aplicado = models.IntegerField(default=0)
    
    # Control de Pagos
    abono_pagado = models.IntegerField(default=0)
    metodo_pago = models.CharField(max_length=10, choices=METODOS_PAGO, default='SITIO')
    referencia_pago = models.CharField(max_length=100, blank=True, null=True) # Sirve para Bold o comprobante Nequi
    
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    fecha_hora_inicio = models.DateTimeField()
    fecha_hora_fin = models.DateTimeField()
    creado_en = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=1, choices=ESTADOS, default='C')
    
    def enviar_notificacion_telegram(self):
        try:
            if self.peluqueria.telegram_token and self.peluqueria.telegram_chat_id:
                msg = f"🔥 *NUEVA CITA ({self.metodo_pago})*\nCliente: {self.cliente_nombre}\nTotal: ${self.precio_total}\nFecha: {self.fecha_hora_inicio}"
                requests.post(f"https://api.telegram.org/bot{self.peluqueria.telegram_token}/sendMessage", data={"chat_id": self.peluqueria.telegram_chat_id, "text": msg, "parse_mode": "Markdown"})
        except: pass

class Cupon(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='cupones')
    codigo = models.CharField(max_length=50)
    porcentaje_descuento = models.IntegerField(default=10)
    activo = models.BooleanField(default=True)
    usos_restantes = models.IntegerField(default=100)

class PerfilUsuario(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.SET_NULL, null=True, blank=True)
    es_dueño = models.BooleanField(default=False)

@receiver(post_save, sender=User)
def crear_perfil(sender, instance, created, **kwargs):
    if created: PerfilUsuario.objects.get_or_create(user=instance)
