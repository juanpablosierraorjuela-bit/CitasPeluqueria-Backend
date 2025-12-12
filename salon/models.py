from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify
from django.utils import timezone
import requests
import pytz 

# Definir zona horaria Colombia para cálculos precisos
ZONA_CO = pytz.timezone('America/Bogota')

class ConfiguracionPlataforma(models.Model):
    solo_un_registro = models.CharField(max_length=1, default='X', editable=False)
    link_pago_bold = models.URLField("Link Respaldo", default="https://checkout.bold.co/payment/LNK_QZ5NWWY82P")
    bold_secret_key = models.CharField(max_length=255, blank=True, null=True)
    telegram_token = models.CharField(max_length=255, blank=True)
    telegram_chat_id = models.CharField(max_length=255, blank=True)
    precio_mensualidad = models.IntegerField(default=130000)
    class Meta: verbose_name_plural = "Configuración Dueño PASO"
    def __str__(self): return "Configuración Plataforma"

class Peluqueria(models.Model):
    nombre = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    nombre_visible = models.CharField(max_length=200, default="Mi Salón")
    ciudad = models.CharField(max_length=100, default="Tunja")
    direccion = models.CharField(max_length=200, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    codigo_pais_wa = models.CharField(max_length=5, default="57")
    
    # Pagos
    porcentaje_abono = models.IntegerField(default=50, help_text="Porcentaje mínimo para reservar (ej: 50)")
    bold_api_key = models.CharField("Llave de Identidad (Bold)", max_length=255, blank=True, null=True)
    bold_secret_key = models.CharField("Llave Secreta (Bold)", max_length=255, blank=True, null=True)
    nequi_celular = models.CharField(max_length=20, blank=True, null=True)
    nequi_qr_imagen = models.ImageField(upload_to='qrs_nequi/', blank=True, null=True)
    
    fecha_inicio_contrato = models.DateTimeField(default=timezone.now)
    activo_saas = models.BooleanField(default=True)
    
    telegram_token = models.CharField(max_length=200, blank=True, null=True)
    telegram_chat_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Horarios
    hora_apertura = models.TimeField(default="08:00")
    hora_cierre = models.TimeField(default="20:00")
    latitud = models.FloatField(default=5.5353)
    longitud = models.FloatField(default=-73.3678)

    @property
    def acepta_pagos_digitales(self): 
        return bool(self.bold_secret_key) or bool(self.nequi_celular)
    
    @property
    def esta_abierto(self):
        """Calcula si está abierto basándose en la hora de Colombia"""
        ahora_co = timezone.now().astimezone(ZONA_CO).time()
        return self.hora_apertura <= ahora_co <= self.hora_cierre

    def save(self, *args, **kwargs):
        if not self.slug: self.slug = slugify(self.nombre)
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
    creado_en = models.DateTimeField(default=timezone.now)

class Cita(models.Model):
    ESTADOS = [('P', 'Pendiente'), ('C', 'Confirmada'), ('X', 'Cancelada')]
    METODOS = [('BOLD', 'Bold'), ('NEQUI', 'Nequi'), ('SITIO', 'En Sitio')]
    TIPO_COBRO = [('TOTAL', 'Pago Completo'), ('ABONO', 'Solo Abono')] # Nuevo campo

    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='citas')
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    servicios = models.ManyToManyField(Servicio)
    cliente_nombre = models.CharField(max_length=150)
    cliente_telefono = models.CharField(max_length=20)
    fecha_hora_inicio = models.DateTimeField()
    fecha_hora_fin = models.DateTimeField()
    
    precio_total = models.IntegerField(default=0)
    abono_pagado = models.IntegerField(default=0)
    
    metodo_pago = models.CharField(max_length=10, choices=METODOS, default='SITIO')
    tipo_cobro = models.CharField(max_length=10, choices=TIPO_COBRO, default='TOTAL') # Nuevo
    referencia_pago = models.CharField(max_length=100, blank=True, null=True)
    
    estado = models.CharField(max_length=1, choices=ESTADOS, default='C')
    creado_en = models.DateTimeField(auto_now_add=True)

    @property
    def saldo_pendiente(self): return self.precio_total - self.abono_pagado

    def enviar_notificacion_telegram(self):
        try:
            if self.peluqueria.telegram_token and self.peluqueria.telegram_chat_id:
                servicios_str = ", ".join([s.nombre for s in self.servicios.all()])
                total_fmt = "{:,.0f}".format(self.precio_total).replace(",", ".")
                abono_fmt = "{:,.0f}".format(self.abono_pagado).replace(",", ".")
                saldo_fmt = "{:,.0f}".format(self.saldo_pendiente).replace(",", ".")
                
                # Convertir hora a Colombia para el mensaje
                fecha_co = self.fecha_hora_inicio.astimezone(ZONA_CO)
                fecha_fmt = fecha_co.strftime("%d/%m/%Y %I:%M %p")
                
                msg = (f"🔥 *NUEVA CITA CONFIRMADA*\n📅 *Fecha:* {fecha_fmt}\n👤 *Cliente:* {self.cliente_nombre}\n"
                       f"📞 *Tel:* {self.cliente_telefono}\n💇 *Staff:* {self.empleado.nombre}\n\n"
                       f"📋 *Servicios:* {servicios_str}\n💰 *Total:* ${total_fmt}\n"
                       f"💳 *Abono ({self.metodo_pago}):* ${abono_fmt}\n📉 *Resta por cobrar:* ${saldo_fmt}")
                requests.post(f"https://api.telegram.org/bot{self.peluqueria.telegram_token}/sendMessage", 
                              data={"chat_id": self.peluqueria.telegram_chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=5)
        except Exception as e: print(f"Error Telegram: {e}")

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
