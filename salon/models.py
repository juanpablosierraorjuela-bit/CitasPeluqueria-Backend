import requests
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.utils.text import slugify
from datetime import timedelta, datetime

# NOTA: La lógica de Telegram se ha hecho autónoma por Peluquería (Correcto).

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
    # duracion es DurationField (Correcto para cálculos de tiempo)
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

# Los días de la semana deben empezar en 0 para Python/Django
DIAS_SEMANA = ((0,'Lunes'),(1,'Martes'),(2,'Miércoles'),(3,'Jueves'),(4,'Viernes'),(5,'Sábado'),(6,'Domingo'))

class HorarioSemanal(models.Model):
    # La peluquería se asigna automáticamente (FIX: Aseguramos que no se pueda modificar en el Admin)
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, blank=True, null=True)
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='horarios')
    dia_semana = models.IntegerField(choices=DIAS_SEMANA)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    descanso_inicio = models.TimeField(blank=True, null=True)
    descanso_fin = models.TimeField(blank=True, null=True)
    
    class Meta: 
        unique_together = ('empleado', 'dia_semana') 
        verbose_name_plural = "Horarios Semanales" # Mejora Admin

    # FIX: Método save para asegurar la consistencia del tenant
    def save(self, *args, **kwargs):
        if not self.peluqueria_id and self.empleado: 
            self.peluqueria = self.empleado.peluqueria
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.empleado} - {self.get_dia_semana_display()}" # Muestra el nombre del día


# =============================================================
# 3. MODELOS DE CITA Y PERFIL
# =============================================================

class Cita(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE)
    cliente_nombre = models.CharField(max_length=100)
    cliente_telefono = models.CharField(max_length=20)
    
    # FIX: ManyToManyField no necesita blank=True, ya que se llena después
    servicios = models.ManyToManyField(Servicio) 
    
    precio_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    fecha_hora_inicio = models.DateTimeField()
    fecha_hora_fin = models.DateTimeField() # Se calcula sumando la duración total
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
    # FIX: Uso instance.perfil.save() para garantizar que se guarde el perfil si hay cambios en el usuario.
    # No es necesario el hasattr() si la relación es OneToOneField y ya creamos el perfil arriba.
    instance.perfil.save()

@receiver(post_save, sender=Empleado)
def crear_horario_por_defecto(sender, instance, created, **kwargs):
    """Crea un horario de Lunes a Domingo por defecto al añadir un nuevo empleado."""
    if created:
        # Aseguramos que la peluquería esté asignada
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

# --- NOTIFICACIÓN AUTÓNOMA POR PELUQUERÍA ---
# FIX: Usamos m2m_changed en Cita.servicios para disparar la señal DESPUÉS de que se hayan
# guardado todos los servicios, asegurando que el precio total sea correcto.
@receiver(m2m_changed, sender=Cita.servicios)
def notificar_nueva_cita(sender, instance, action, **kwargs):
    # La señal se dispara una vez que se han añadido los servicios (post_add)
    if action == 'post_add': 
        peluqueria = instance.peluqueria
        token = peluqueria.telegram_token
        chat_id = peluqueria.telegram_chat_id
        
        # FIX: Verificamos que el token y el chat_id existan
        if token and chat_id:
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
            
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {
                "chat_id": chat_id, 
                "text": msg, 
                "parse_mode": "Markdown"
            }
            
            try: 
                # Intentamos la llamada a la API
                response = requests.post(url, data=data, timeout=5)
                # Imprimimos el diagnóstico de la API para saber si falló
                if not response.json().get('ok'):
                    print(f"❌ ERROR TELEGRAM (API) en {peluqueria.nombre}: {response.text}")
                else:
                    print(f"✅ Notificación Telegram enviada a {peluqueria.nombre}")
                    
            except requests.exceptions.RequestException as e: 
                print(f"❌ ERROR DE CONEXIÓN TELEGRAM a {peluqueria.nombre}: {e}")