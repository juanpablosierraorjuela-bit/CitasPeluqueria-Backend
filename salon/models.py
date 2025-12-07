from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify
from datetime import timedelta
import requests # Necesario para Telegram

# =============================================================
# 1. MODELOS BASE
# =============================================================

class Peluqueria(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True, null=True) 
    nombre_visible = models.CharField(max_length=100, default="Mi Salón")
    
    telegram_token = models.CharField(max_length=100, blank=True, null=True)
    telegram_chat_id = models.CharField(max_length=100, blank=True, null=True)
    
    direccion = models.CharField(max_length=200, blank=True, null=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    hora_apertura = models.TimeField(default="08:00")
    hora_cierre = models.TimeField(default="20:00")
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre_visible

class Servicio(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='servicios')
    nombre = models.CharField(max_length=100)
    duracion = models.DurationField(default=timedelta(minutes=30)) 
    precio = models.DecimalField(max_digits=8, decimal_places=2) 
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} (${self.precio})"

# =============================================================
# 2. MODELOS DE HORARIOS Y EMPLEADOS
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

# =============================================================
# 3. MODELOS DE CITA Y PERFIL
# =============================================================

class Cita(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE)
    cliente_nombre = models.CharField(max_length=100)
    cliente_telefono = models.CharField(max_length=20)
    servicios = models.ManyToManyField(Servicio) 
    precio_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    fecha_hora_inicio = models.DateTimeField()
    fecha_hora_fin = models.DateTimeField() 
    estado = models.CharField(max_length=1, choices=[('P','Pendiente'),('C','Confirmada'),('A','Anulada')], default='P')

    def __str__(self):
        return f"Cita {self.cliente_nombre}"

class PerfilUsuario(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.SET_NULL, null=True, blank=True)

# =============================================================
# 4. SEÑALES (LA AUTOMATIZACIÓN)
# =============================================================

@receiver(post_save, sender=User)
def crear_perfil(sender, instance, created, **kwargs):
    if created: PerfilUsuario.objects.create(user=instance)

# --- 🔥 NOTIFICACIÓN TELEGRAM AUTOMÁTICA 🔥 ---
@receiver(post_save, sender=Cita)
def notificar_cita_telegram(sender, instance, created, **kwargs):
    """
    Cada vez que se guarda una cita (created=True), envía mensaje a Telegram.
    Funciona desde Admin, App, Web, etc.
    """
    if created and instance.estado == 'C': # Solo si es nueva y confirmada
        try:
            peluqueria = instance.peluqueria
            token = peluqueria.telegram_token
            chat_id = peluqueria.telegram_chat_id
            
            if not token or not chat_id: return

            # Calculamos servicios (si es m2m, a veces requiere un pequeño delay o signal m2m_changed,
            # pero para simplificar intentaremos leerlos, si no están vacíos)
            # Nota: En many-to-many, los datos se guardan después del save(). 
            # El mensaje saldrá básico y podríamos mejorarlo con m2m_changed, 
            # pero esto asegura que AL MENOS avise.
            
            mensaje = (
                f"🔔 *NUEVA CITA AGENDADA*\n\n"
                f"👤 {instance.cliente_nombre}\n"
                f"📞 {instance.cliente_telefono}\n"
                f"📅 {instance.fecha_hora_inicio.strftime('%d/%m/%Y %H:%M')}\n"
                f"✂️ {instance.empleado.nombre}\n"
                f"💰 ${instance.precio_total}\n"
            )

            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, data={"chat_id": chat_id, "text": mensaje, "parse_mode": "Markdown"}, timeout=3)
        except Exception as e:
            print(f"Error Telegram Signal: {e}")