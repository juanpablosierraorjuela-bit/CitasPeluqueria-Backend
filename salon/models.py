import requests
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.utils.text import slugify
from datetime import timedelta, datetime

# NOTA: Se eliminaron las variables globales de Telegram para permitir
# que cada peluquería use su propio bot de forma autónoma.

class Peluqueria(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True, null=True) 
    nombre_visible = models.CharField(max_length=100, default="Mi Salón")
    
    # --- CONFIGURACIÓN TELEGRAM AUTÓNOMA ---
    # Cada dueño pone aquí SU propio token y SU propio ID
    telegram_token = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="Token del bot creado con @BotFather"
    )
    telegram_chat_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="ID de chat del dueño para recibir avisos"
    )
    
    # --- DATOS DE CONTACTO ---
    direccion = models.CharField(max_length=200, blank=True, null=True, help_text="Ej: Calle 123 #45-67")
    telefono = models.CharField(max_length=50, blank=True, null=True, help_text="Ej: +57 300 123 4567")
    
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

# --- SEÑALES ---

@receiver(post_save, sender=User)
def crear_perfil(sender, instance, created, **kwargs):
    if created:
        PerfilUsuario.objects.create(user=instance)
    # Evitamos error si el perfil ya existe al guardar de nuevo
    if hasattr(instance, 'perfil'):
        instance.perfil.save()

@receiver(post_save, sender=Empleado)
def crear_horario_por_defecto(sender, instance, created, **kwargs):
    if created:
        for dia_num, _ in DIAS_SEMANA:
            if not HorarioSemanal.objects.filter(empleado=instance, dia_semana=dia_num).exists():
                HorarioSemanal.objects.create(
                    peluqueria=instance.peluqueria, 
                    empleado=instance, 
                    dia_semana=dia_num, 
                    hora_inicio="09:00", 
                    hora_fin="18:00", 
                    descanso_inicio="12:00", 
                    descanso_fin="13:00"
                )

# --- NOTIFICACIÓN AUTÓNOMA POR PELUQUERÍA ---
@receiver(m2m_changed, sender=Cita.servicios)
def notificar_nueva_cita(sender, instance, action, **kwargs):
    if action == 'post_add': 
        # 1. Obtenemos la peluquería específica de esta cita
        peluqueria = instance.peluqueria
        
        # 2. Verificamos si ESTA peluquería tiene configurado su bot
        token = peluqueria.telegram_token
        chat_id = peluqueria.telegram_chat_id
        
        if token and chat_id:
            # Preparamos los datos
            servicios_nombres = ", ".join([s.nombre for s in instance.servicios.all()])
            msg = (
                f"💈 *NUEVA CITA EN {peluqueria.nombre_visible.upper()}*\n\n"
                f"👤 *Cliente:* {instance.cliente_nombre}\n"
                f"📱 *Tel:* {instance.cliente_telefono}\n"
                f"💇 *Servicios:* {servicios_nombres}\n"
                f"💰 *Total:* ${instance.precio_total}\n"
                f"✂️ *Estilista:* {instance.empleado.nombre}\n"
                f"📅 *Fecha:* {instance.fecha_hora_inicio.strftime('%d/%m/%Y %H:%M')}"
            )
            
            # 3. Enviamos usando EL TOKEN DE LA PELUQUERÍA
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {
                "chat_id": chat_id, 
                "text": msg, 
                "parse_mode": "Markdown"
            }
            
            try: 
                requests.post(url, data=data, timeout=5)
            except requests.exceptions.RequestException as e: 
                print(f"Error enviando Telegram a {peluqueria.nombre}: {e}")