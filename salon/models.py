from django.db import models
from django.contrib.auth.models import User
import uuid

class Tenant(models.Model):
    # ... tus campos existentes (name, subdomain, etc) ...

    class Meta:
        verbose_name = "Peluquería"
        verbose_name_plural = "Peluquerías"

class Professional(models.Model):
    # ... tus campos ...

    class Meta:
        verbose_name = "Profesional"
        verbose_name_plural = "Profesionales"

class Service(models.Model):
    # ... tus campos ...

    class Meta:
        verbose_name = "Servicio"
        verbose_name_plural = "Servicios"

class Product(models.Model):
    # ... tus campos ...

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"

class Appointment(models.Model):
    # ... tus campos ...

    class Meta:
        verbose_name = "Cita"
        verbose_name_plural = "Citas Reservadas"

class ExternalPayment(models.Model):
    # ... tus campos ...
    
    class Meta:
        verbose_name = "Pago Externo"
        verbose_name_plural = "Pagos a Profesionales"
