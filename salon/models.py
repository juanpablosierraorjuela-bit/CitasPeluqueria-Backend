import requests 
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify
from datetime import timedelta, datetime

# ==========================================
# CONFIGURACIÓN DE TELEGRAM
# ==========================================
TELEGRAM_BOT_TOKEN = '8430924416:AAHZoFzoeRE1bTLPZ9KNDjIsK6sDzfs0ag8' 
TELEGRAM_GLOBAL_CHAT_ID = '8345213799' 

# 1. MODELO PELUQUERÍA
class Peluqueria(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True, null=True) 
    nombre_visible = models.CharField(max_length=100, default="Mi Salón")
    telegram_chat_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Horarios globales del negocio
    hora_apertura = models.TimeField(default="08:00")
    hora_cierre = models.TimeField(default="20:00")
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre

# 2. MODELOS TRANSACCIONALES

class Servicio(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='servicios')
    nombre = models.CharField(max_length=100)
    duracion = models.DurationField(default=timedelta(minutes=30), help_text="Duración estimada")
    precio = models.DecimalField(max_digits=8, decimal_places=2) 
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} - {self.peluqueria}"

class Empleado(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='empleados')
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    servicios_que_realiza = models.ManyToManyField(Servicio)
    
    def __str__(self):
        return f"{self.nombre} {self.apellido}"

# Días de la semana
DIAS_SEMANA = (
    (0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'),
    (3, 'Jueves'), (4, 'Viernes'), (5, 'Sábado'), (6, 'Domingo'),
)

class HorarioSemanal(models.Model):
    # Nota: Agregamos blank=True, null=True para evitar errores de validación, 
    # aunque el método save() se encarga de llenarlo siempre.
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, blank=True, null=True)
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='horarios')
    dia_semana = models.IntegerField(choices=DIAS_SEMANA)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    descanso_inicio = models.TimeField(blank=True, null=True, help_text="Inicio hora almuerzo (opcional)")
    descanso_fin = models.TimeField(blank=True, null=True, help_text="Fin hora almuerzo (opcional)")
    
    class Meta:
        unique_together = ('empleado', 'dia_semana') 

    # --- ESTO ARREGLA TU ERROR ---
    def save(self, *args, **kwargs):
        # Si el horario no tiene peluquería asignada, copiamos la del empleado
        if not self.peluqueria_id and self.empleado:
            self.peluqueria = self.empleado.peluqueria
        super().save(*args, **kwargs)
    # -----------------------------

    def __str__(self):
        return f"{self.empleado} - Día {self.dia_semana}"

class Cita(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE)
    cliente_nombre = models.CharField(max_length=100)
    cliente_telefono = models.CharField(max_length=20)
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE)
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    fecha_hora_inicio = models.DateTimeField()
    fecha_hora_fin = models.DateTimeField()
    
    ESTADOS = [('P', 'Pendiente'), ('C', 'Confirmada'), ('A', 'Anulada')]
    estado = models.CharField(max_length=1, choices=ESTADOS, default='P')

    def __str__(self):
        return f"Cita {self.cliente_nombre}"

class PerfilUsuario(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.peluqueria}"

# ==========================================
# SEÑALES (AUTOMATIZACIÓN)
# ==========================================

@receiver(post_save, sender=User)
def crear_perfil(sender, instance, created, **kwargs):
    if created:
        PerfilUsuario.objects.create(user=instance)
    instance.perfil.save()

@receiver(post_save, sender=Empleado)
def crear_horario_por_defecto(sender, instance, created, **kwargs):
    """
    Crea automáticamente horarios de Lunes a Domingo (09:00-18:00)
    cuando se registra un nuevo empleado.
    """
    if created:
        for dia_num, dia_nombre in DIAS_SEMANA:
            # Verificamos si ya existe para no duplicar
            if not HorarioSemanal.objects.filter(empleado=instance, dia_semana=dia_num).exists():
                HorarioSemanal.objects.create(
                    peluqueria=instance.peluqueria, # Aquí sí se pasa explícitamente
                    empleado=instance,
                    dia_semana=dia_num,
                    hora_inicio="09:00",
                    hora_fin="18:00",
                    descanso_inicio="12:00",
                    descanso_fin="13:00"
                )

@receiver(post_save, sender=Cita)
def notificar_nueva_cita(sender, instance, created, **kwargs):
    if created:
        chat_id_destino = instance.peluqueria.telegram_chat_id or TELEGRAM_GLOBAL_CHAT_ID
        
        if chat_id_destino and TELEGRAM_BOT_TOKEN:
            fecha_fmt = instance.fecha_hora_inicio.strftime('%d/%m/%Y %H:%M')
            mensaje = (
                f"🔔 *NUEVA CITA AGENDADA*\n\n"
                f"🏢 *Salón:* {instance.peluqueria.nombre_visible}\n"
                f"👤 *Cliente:* {instance.cliente_nombre}\n"
                f"📱 *Tel:* {instance.cliente_telefono}\n"
                f"💇 *Servicio:* {instance.servicio.nombre}\n"
                f"✂️ *Estilista:* {instance.empleado.nombre}\n"
                f"📅 *Fecha:* {fecha_fmt}"
            )
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {"chat_id": chat_id_destino, "text": mensaje, "parse_mode": "Markdown"}
            try:
                requests.post(url, data=data, timeout=5)
                print(f"✅ Telegram enviado a {chat_id_destino}")
            except Exception as e:
                print(f"❌ Error enviando Telegram: {e}")