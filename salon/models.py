import requests
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.utils.text import slugify
from datetime import timedelta, datetime

# =============================================================
# 0. FUNCIONES REUTILIZABLES (Diagnóstico de Telegram)
# =============================================================

def enviar_mensaje_telegram(token, chat_id, mensaje):
    """Función central para enviar cualquier mensaje a Telegram."""
    if not token or not chat_id:
        return False, "Token o Chat ID no configurados."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, data=data, timeout=5)
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get('ok'):
            return True, "Mensaje enviado con éxito."
        else:
            error_msg = response_data.get('description', 'Error desconocido de la API.')
            # Aquí imprimimos el error de la API para el diagnóstico
            print(f"❌ ERROR TELEGRAM (API): {error_msg}. Respuesta: {response.text}")
            return False, f"Error de la API: {error_msg}"

    except requests.exceptions.RequestException as e:
        return False, f"Error de conexión de red: {e}"


# =============================================================
# 1. MODELOS BASE
# =============================================================

class Peluqueria(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True, null=True) 
    nombre_visible = models.CharField(max_length=100, default="Mi Salón")
    
    # --- CONFIGURACIÓN TELEGRAM AUTÓNOMA ---
    telegram_token = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="Token del bot (ej: 123456:ABC-DEF)"
    )
    telegram_chat_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="ID de chat del dueño/grupo (ej: -123456789)"
    )
    
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
        verbose_name_plural = "Horarios Semanales"

    def save(self, *args, **kwargs):
        if not self.peluqueria_id and self.empleado: 
            self.peluqueria = self.empleado.peluqueria
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.empleado} - {self.get_dia_semana_display()}"


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
    
    def __str__(self):
        return f"{self.user.username} - {self.peluqueria}"

# =============================================================
# 4. SEÑALES (Automatización y Telegram)
# =============================================================

@receiver(post_save, sender=User)
def crear_perfil(sender, instance, created, **kwargs):
    if created:
        PerfilUsuario.objects.create(user=instance)
    # FIX: Se guarda el perfil para reflejar cambios en el usuario (ej: password)
    instance.perfil.save()

@receiver(post_save, sender=Empleado)
def crear_horario_por_defecto(sender, instance, created, **kwargs):
    """Crea un horario de Lunes a Domingo por defecto al añadir un nuevo empleado."""
    if created:
        peluqueria = instance.peluqueria
        
        for dia_num, _ in DIAS_SEMANA:
            # FIX: Aseguramos que solo se creen si no existen, para evitar conflictos
            if not HorarioSemanal.objects.filter(empleado=instance, dia_semana=dia_num).exists():
                HorarioSemanal.objects.create(
                    peluqueria=peluqueria, 
                    empleado=instance, 
                    dia_semana=dia_num, 
                    hora_inicio="09:00", 
                    hora_fin="18:00", 
                    descanso_inicio="12:00", 
                    descanso_fin="13:00"
                )

@receiver(m2m_changed, sender=Cita.servicios)
def notificar_nueva_cita(sender, instance, action, **kwargs):
    """Dispara la notificación de Telegram usando la configuración de la Peluquería."""
    if action == 'post_add': 
        peluqueria = instance.peluqueria
        token = peluqueria.telegram_token
        chat_id = peluqueria.telegram_chat_id
        
        if token and chat_id:
            servicios_nombres = ", ".join([s.nombre for s in instance.servicios.all()])
            
            mensaje = (
                f"💈 *NUEVA CITA EN {peluqueria.nombre_visible.upper()}*\n\n"
                f"👤 *Cliente:* {instance.cliente_nombre}\n"
                f"📱 *Tel:* {instance.cliente_telefono or 'No proporcionado'}\n"
                f"💇 *Servicios:* {servicios_nombres}\n"
                f"💰 *Total:* ${instance.precio_total}\n"
                f"✂️ *Estilista:* {instance.empleado.nombre}\n"
                f"📅 *Fecha:* {instance.fecha_hora_inicio.strftime('%d/%m/%Y %H:%M')}"
            )
            
            # Llamamos a la función central y diagnosticamos el error si falla
            exito, mensaje_resultado = enviar_mensaje_telegram(token, chat_id, mensaje)
            
            if not exito:
                print(f"❌ FALLO DE NOTIFICACIÓN para {peluqueria.nombre}: {mensaje_resultado}")