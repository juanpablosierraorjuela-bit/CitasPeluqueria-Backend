import os
import sys

# --- CONFIGURACIÓN ---
APP_NAME = 'core'  

def write_file(filename, content):
    path = os.path.join(APP_NAME, filename)
    if not os.path.exists(APP_NAME):
        print(f"Error: No encuentro la carpeta {APP_NAME}. Verifica que estás en la raíz.")
        return
    print(f"Reparando {path}...")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

print("--- INICIANDO REPARACIÓN TOTAL DEL SISTEMA PASO ---")

# ==========================================
# 1. CORE/MODELS.PY 
# ==========================================
models_code = """from django.db import models
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
"""
write_file('models.py', models_code)

# ==========================================
# 2. CORE/VIEWS.PY
# ==========================================
views_code = """from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Tenant, Professional, Service, Product, Appointment, ExternalPayment
from django.contrib import messages
from django.db.models import Sum
from django.contrib.auth.models import User

@login_required
def dashboard(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    if not tenant: return render(request, 'core/create_tenant.html')
    
    professionals = Professional.objects.filter(tenant=tenant)
    external_pros = professionals.filter(is_external=True)
    internal_pros = professionals.filter(is_external=False)
    services = Service.objects.filter(tenant=tenant)
    products = Product.objects.filter(tenant=tenant)
    appointments = Appointment.objects.filter(tenant=tenant).order_by('-date', '-time')
    
    total_sales = appointments.filter(status='COMPLETED').aggregate(Sum('service__price'))['service__price__sum'] or 0

    context = {
        'tenant': tenant,
        'professionals': professionals,
        'internal_pros': internal_pros,
        'external_pros': external_pros,
        'services': services,
        'products': products,
        'appointments': appointments,
        'total_sales': total_sales,
        'show_inventory': True,
        'show_settings': True,
        'show_notifications': True,
        'show_steps': True,
    }
    return render(request, 'core/dashboard.html', context)

@login_required
def inventory_list(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    products = Product.objects.filter(tenant=tenant)
    return render(request, 'core/inventory_list.html', {'products': products})

@login_required
def add_product(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    if request.method == 'POST':
        name = request.POST.get('name')
        price = request.POST.get('price')
        stock = request.POST.get('stock')
        Product.objects.create(tenant=tenant, name=name, price=price, stock=stock)
        messages.success(request, 'Producto añadido')
        return redirect('dashboard')
    return render(request, 'core/add_product.html')

@login_required
def invite_external(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    if request.method == 'POST':
        name = request.POST.get('name')
        commission = request.POST.get('commission')
        pro = Professional.objects.create(tenant=tenant, name=name, phone="000", is_external=True, commission_rate=commission)
        domain = request.build_absolute_uri('/')[:-1] 
        link = f"{domain}/register-external/{pro.invite_token}/"
        messages.success(request, f"Link creado: {link}")
        return redirect('dashboard')
    return redirect('dashboard')

def register_external_view(request, token):
    pro = get_object_or_404(Professional, invite_token=token)
    if request.method == 'POST':
        phone = request.POST.get('phone')
        payment_info = request.POST.get('payment_info')
        telegram = request.POST.get('telegram')
        password = request.POST.get('password')
        pro.phone = phone
        pro.payment_info = payment_info
        pro.telegram_chat_id = telegram
        if not User.objects.filter(username=phone).exists():
            user = User.objects.create_user(username=phone, password=password)
            pro.user = user
        pro.save()
        messages.success(request, "Registro Exitoso")
        return redirect('login')
    return render(request, 'core/register_external.html', {'pro': pro})

@login_required
def pay_external(request, pro_id):
    pro = get_object_or_404(Professional, id=pro_id)
    if request.method == 'POST':
        amount = float(request.POST.get('amount'))
        ExternalPayment.objects.create(professional=pro, amount=amount)
        pro.balance_due = float(pro.balance_due) - amount
        pro.save()
        messages.success(request, f"Pago registrado")
    return redirect('dashboard')

@login_required
def settings_view(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    if request.method == 'POST':
        tenant.nequi_number = request.POST.get('nequi')
        tenant.bold_api_key = request.POST.get('bold')
        tenant.save()
        messages.success(request, "Configuración guardada")
    return render(request, 'core/settings.html', {'tenant': tenant})
"""
write_file('views.py', views_code)

# ==========================================
# 3. CORE/URLS.PY
# ==========================================
urls_code = """from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('settings/', views.settings_view, name='settings'),
    path('inventory/', views.inventory_list, name='inventory'),
    path('inventory/add/', views.add_product, name='add_product'),
    path('invite-pro/', views.invite_external, name='invite_external'),
    path('register-external/<uuid:token>/', views.register_external_view, name='register_external'),
    path('pay-pro/<int:pro_id>/', views.pay_external, name='pay_external'),
]
"""
write_file('urls.py', urls_code)

# ==========================================
# 4. CORE/ADMIN.PY
# ==========================================
admin_code = """from django.contrib import admin
from .models import Tenant, Professional, Service, Product, Appointment, ExternalPayment
admin.site.register(Professional)
admin.site.register(Tenant)
admin.site.register(Service)
admin.site.register(Product)
admin.site.register(Appointment)
admin.site.register(ExternalPayment)
"""
write_file('admin.py', admin_code)

print("--- ARCHIVOS REPARADOS ---")
try:
    os.system('git add .')
    os.system('git commit -m "Reparacion Automatica"')
    os.system('git push origin main')
    print("SUBIDO A GITHUB EXITOSAMENTE.")
except:
    print("Error en Git, revisa credenciales.")
