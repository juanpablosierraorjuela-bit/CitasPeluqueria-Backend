from django.db import models
from django.contrib.auth.models import User
import uuid

class Tenant(models.Model):
    users = models.ManyToManyField(User, related_name='tenants')
    name = models.CharField(max_length=100, verbose_name="Nombre del Salón")
    subdomain = models.CharField(max_length=100, unique=True)
    address = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    nequi_number = models.CharField(max_length=20, blank=True, verbose_name="Nequi del Negocio")
    bold_api_key = models.CharField(max_length=200, blank=True, verbose_name="Api Key Bold")
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.name

class Professional(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    photo = models.ImageField(upload_to='profesionales/', blank=True, null=True)
    
    # LOGICA DOMICILIARIO
    is_external = models.BooleanField(default=False, verbose_name="Es Domiciliario Externo")
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name="% Comisión Dueño")
    payment_info = models.TextField(blank=True, verbose_name="Datos Bancarios")
    telegram_chat_id = models.CharField(max_length=50, blank=True, null=True, verbose_name="ID Telegram")
    invite_token = models.UUIDField(default=uuid.uuid4, editable=False)
    balance_due = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Saldo a Pagar")

    def __str__(self): return self.name

class Service(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_min = models.IntegerField(default=30)
    def __str__(self): return f"{self.name} - ${self.price}"

class Product(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    def __str__(self): return self.name

class Appointment(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=20)
    date = models.DateField()
    time = models.TimeField()
    STATUS_CHOICES = [('PENDING', 'Pendiente'), ('CONFIRMED', 'Confirmada'), ('COMPLETED', 'Completada'), ('CANCELLED', 'Cancelada')]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    is_delivery = models.BooleanField(default=False, verbose_name="Es Domicilio")
    address_delivery = models.TextField(blank=True, null=True, verbose_name="Dirección Domicilio")
    def __str__(self): return f"{self.customer_name} - {self.status}"

class ExternalPayment(models.Model):
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date_paid = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
