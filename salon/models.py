from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify

class Tenant(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tenants', verbose_name="Dueño")
    name = models.CharField(max_length=100, verbose_name="Nombre del Negocio")
    subdomain = models.SlugField(unique=True, verbose_name="Identificador (URL)")
    ciudad = models.CharField(max_length=100, default="Tunja", verbose_name="Ciudad")
    direccion = models.CharField(max_length=200, blank=True, null=True, verbose_name="Dirección")
    # CORREGIDO: Aumentado de 20 a 50
    telefono = models.CharField(max_length=50, blank=True, null=True, verbose_name="Teléfono")
    
    # Redes y Pagos
    instagram = models.URLField(blank=True, null=True, verbose_name="Instagram")
    facebook = models.URLField(blank=True, null=True, verbose_name="Facebook")
    tiktok = models.URLField(blank=True, null=True, verbose_name="TikTok")
    # CORREGIDO: Aumentado de 20 a 50
    nequi_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="Nequi")
    bold_api_key = models.CharField(max_length=200, blank=True, null=True, verbose_name="API Key Bold")

    class Meta:
        verbose_name = "Negocio"
        verbose_name_plural = "Negocios"

    def __str__(self):
        return self.name

class Professional(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='professionals')
    nombre = models.CharField(max_length=100, verbose_name="Nombre Completo")
    especialidad = models.CharField(max_length=100, blank=True, verbose_name="Especialidad")
    email = models.EmailField(blank=True, null=True, verbose_name="Correo Electrónico")
    # CORREGIDO: Aumentado de 20 a 50
    telefono = models.CharField(max_length=50, blank=True, null=True, verbose_name="Teléfono")
    
    # Vinculación opcional con usuario de sistema para login
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='professional_profile')

    class Meta:
        verbose_name = "Profesional"
        verbose_name_plural = "Profesionales"

    def __str__(self):
        return self.nombre

class Service(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='services')
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Servicio")
    precio = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio")
    duracion = models.IntegerField(help_text="Duración en minutos", verbose_name="Duración (min)")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")

    class Meta:
        verbose_name = "Servicio"
        verbose_name_plural = "Servicios"

    def __str__(self):
        return f"{self.nombre} - ${self.precio}"

class Product(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='products')
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Producto")
    precio = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio")
    stock = models.IntegerField(default=0, verbose_name="Cantidad Disponible")

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Inventario"

    def __str__(self):
        return self.nombre

class Appointment(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('confirmada', 'Confirmada'),
        ('cancelada', 'Cancelada'),
        ('completada', 'Completada'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='appointments')
    servicio = models.ForeignKey(Service, on_delete=models.CASCADE, verbose_name="Servicio")
    empleado = models.ForeignKey(Professional, on_delete=models.CASCADE, verbose_name="Profesional")
    fecha_hora_inicio = models.DateTimeField(verbose_name="Fecha y Hora")
    cliente_nombre = models.CharField(max_length=100, verbose_name="Nombre Cliente")
    # CORREGIDO: Aumentado de 20 a 50
    cliente_telefono = models.CharField(max_length=50, verbose_name="Teléfono Cliente")
    cliente_email = models.EmailField(blank=True, null=True, verbose_name="Email Cliente")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    precio_total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total a Pagar")

    class Meta:
        verbose_name = "Cita"
        verbose_name_plural = "Citas"

    def __str__(self):
        return f"{self.cliente_nombre} - {self.fecha_hora_inicio}"

class ExternalPayment(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    referencia = models.CharField(max_length=100)
    fecha = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, default='pendiente')

    class Meta:
        verbose_name = "Pago Externo"
        verbose_name_plural = "Pagos Externos"

class Absence(models.Model):
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name='absences', verbose_name="Profesional")
    fecha_inicio = models.DateTimeField(verbose_name="Inicio Ausencia")
    fecha_fin = models.DateTimeField(verbose_name="Fin Ausencia")
    motivo = models.CharField(max_length=200, blank=True, verbose_name="Motivo")

    class Meta:
        verbose_name = "Ausencia"
        verbose_name_plural = "Ausencias"
        ordering = ['fecha_inicio']

    def __str__(self):
        return f"{self.professional.nombre}: {self.motivo}"
