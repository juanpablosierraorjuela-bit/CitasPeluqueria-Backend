import os
import sys

# --- CONFIGURACIÓN CORRECTA ---
APP_NAME = 'salon'  # Tu app se llama salon, no core
PROJECT_NAME = 'salon_project'

def write_file(path, content):
    # Asegurar que el directorio exista
    os.makedirs(os.path.dirname(path), exist_ok=True)
    print(f"Reparando {path}...")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

print("--- 🔮 INICIANDO HECHIZO DE REPARACIÓN (MODO EXPERTO) ---")

# ==========================================
# 1. SALON/MODELS.PY (Asegurando consistencia)
# ==========================================
models_code = """from django.db import models
from django.contrib.auth.models import User
import uuid

class Tenant(models.Model):
    users = models.ManyToManyField(User, related_name='tenants')
    name = models.CharField(max_length=100, verbose_name="Nombre del Salón")
    subdomain = models.CharField(max_length=100, unique=True, verbose_name="Identificador (Slug)")
    address = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    # Datos Públicos
    ciudad = models.CharField(max_length=100, default="Tunja")
    latitud = models.FloatField(default=0.0)
    longitud = models.FloatField(default=0.0)
    instagram = models.URLField(blank=True)
    facebook = models.URLField(blank=True)
    tiktok = models.URLField(blank=True)
    
    # Configuración de Pagos
    nequi_number = models.CharField(max_length=20, blank=True, verbose_name="Nequi del Negocio")
    bold_api_key = models.CharField(max_length=200, blank=True, verbose_name="Api Key Bold")
    
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def slug(self):
        return self.subdomain

    def __str__(self): return self.name

class Professional(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    photo = models.ImageField(upload_to='profesionales/', blank=True, null=True)
    is_external = models.BooleanField(default=False)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    payment_info = models.TextField(blank=True)
    telegram_chat_id = models.CharField(max_length=50, blank=True, null=True)
    invite_token = models.UUIDField(default=uuid.uuid4, editable=False)
    balance_due = models.DecimalField(max_digits=10, decimal_places=2, default=0)
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
    status = models.CharField(max_length=20, default='PENDING')
    is_delivery = models.BooleanField(default=False)
    address_delivery = models.TextField(blank=True, null=True)
    def __str__(self): return f"{self.customer_name} - {self.status}"

class ExternalPayment(models.Model):
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date_paid = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
"""
write_file(f'{APP_NAME}/models.py', models_code)

# ==========================================
# 2. SALON/VIEWS.PY (Añadiendo Registro y Arreglando Rutas)
# ==========================================
views_code = """from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Tenant, Professional, Service, Product, Appointment, ExternalPayment
from django.contrib import messages
from django.db.models import Sum
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm

# --- VISTA PORTADA ---
def public_home(request):
    peluquerias = Tenant.objects.all()
    ciudades = peluquerias.values_list('ciudad', flat=True).distinct()
    return render(request, 'salon/index.html', {'peluquerias': peluquerias, 'ciudades': ciudades})

# --- VISTA REGISTRO (SIGNUP) ---
def signup_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})

# --- VISTA PARA AGENDAR ---
def booking_page(request, slug):
    tenant = get_object_or_404(Tenant, subdomain=slug)
    services = Service.objects.filter(tenant=tenant)
    pros = Professional.objects.filter(tenant=tenant)
    return render(request, 'salon/agendar.html', {'tenant': tenant, 'services': services, 'pros': pros})

# --- VISTA LANDING PAGE ---
def landing_saas_view(request):
    if request.user.is_authenticated:
        return redirect('panel_negocio')
    return render(request, 'salon/landing_saas.html')

# --- DASHBOARD ---
@login_required
def dashboard(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    
    # Si no tiene negocio, mostramos pantalla de creación
    if not tenant:
        if request.method == 'POST':
            name = request.POST.get('name')
            subdomain = request.POST.get('subdomain')
            # Validación básica
            if Tenant.objects.filter(subdomain=subdomain).exists():
                messages.error(request, "Este ID ya está en uso.")
            else:
                new_tenant = Tenant.objects.create(name=name, subdomain=subdomain)
                new_tenant.users.add(request.user)
                new_tenant.save()
                return redirect('panel_negocio')
        return render(request, 'salon/create_tenant.html')

    # Si tiene negocio, mostramos el panel
    professionals = Professional.objects.filter(tenant=tenant)
    services = Service.objects.filter(tenant=tenant)
    products = Product.objects.filter(tenant=tenant)
    appointments = Appointment.objects.filter(tenant=tenant).order_by('-date')
    
    context = {
        'tenant': tenant,
        'professionals': professionals,
        'services': services,
        'products': products,
        'appointments': appointments,
    }
    return render(request, 'salon/dashboard.html', context)

# --- CLIENTE AGENDA ---
def client_agenda(request):
    return render(request, 'salon/mi_agenda.html')

# --- HERRAMIENTAS DUEÑO ---
@login_required
def inventory_list(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    products = Product.objects.filter(tenant=tenant) if tenant else []
    return render(request, 'salon/inventory_list.html', {'products': products})

@login_required
def add_product(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    if request.method == 'POST':
        Product.objects.create(
            tenant=tenant, 
            name=request.POST.get('name'), 
            price=request.POST.get('price'), 
            stock=request.POST.get('stock')
        )
        return redirect('inventory')
    return render(request, 'salon/add_product.html')

@login_required
def invite_external(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    if request.method == 'POST':
        pro = Professional.objects.create(
            tenant=tenant, 
            name=request.POST.get('name'), 
            phone="000", 
            is_external=True, 
            commission_rate=request.POST.get('commission')
        )
        domain = request.build_absolute_uri('/')[:-1]
        link = f"{domain}/register-external/{pro.invite_token}/"
        messages.success(request, f"Enlace generado: {link}")
    return redirect('panel_negocio')

def register_external_view(request, token):
    pro = get_object_or_404(Professional, invite_token=token)
    if request.method == 'POST':
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        pro.phone = phone
        pro.payment_info = request.POST.get('payment_info')
        pro.telegram_chat_id = request.POST.get('telegram')
        if not User.objects.filter(username=phone).exists():
            user = User.objects.create_user(username=phone, password=password)
            pro.user = user
        pro.save()
        login(request, pro.user)
        return redirect('panel_negocio')
    return render(request, 'salon/register_external.html', {'pro': pro})

@login_required
def pay_external(request, pro_id):
    pro = get_object_or_404(Professional, id=pro_id)
    if request.method == 'POST':
        amount = float(request.POST.get('amount'))
        ExternalPayment.objects.create(professional=pro, amount=amount)
        pro.balance_due = float(pro.balance_due) - amount
        pro.save()
    return redirect('panel_negocio')

@login_required
def settings_view(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    if request.method == 'POST':
        tenant.nequi_number = request.POST.get('nequi')
        tenant.bold_api_key = request.POST.get('bold')
        tenant.instagram = request.POST.get('instagram')
        tenant.save()
        messages.success(request, "Configuración guardada")
    return render(request, 'salon/settings.html', {'tenant': tenant})
"""
write_file(f'{APP_NAME}/views.py', views_code)

# ==========================================
# 3. SALON/URLS.PY (Mapeo Completo)
# ==========================================
urls_code = """from django.urls import path, include
from . import views

urlpatterns = [
    # Rutas Públicas
    path('', views.public_home, name='home'),
    path('negocios/', views.landing_saas_view, name='landing_saas'),
    path('mi-agenda/', views.client_agenda, name='mi_agenda'),
    
    # Rutas de Autenticación
    path('accounts/', include('django.contrib.auth.urls')),
    path('signup/', views.signup_view, name='signup'), # ¡NUEVA RUTA IMPORTANTE!
    
    # Rutas del Panel
    path('dashboard/', views.dashboard, name='panel_negocio'),
    path('reservar/<slug:slug>/', views.booking_page, name='agendar_cita'),
    
    # Herramientas
    path('settings/', views.settings_view, name='settings'),
    path('inventory/', views.inventory_list, name='inventory'),
    path('inventory/add/', views.add_product, name='add_product'),
    
    # Externos
    path('invite-pro/', views.invite_external, name='invite_external'),
    path('register-external/<uuid:token>/', views.register_external_view, name='register_external'),
    path('pay-pro/<int:pro_id>/', views.pay_external, name='pay_external'),
]
"""
write_file(f'{APP_NAME}/urls.py', urls_code)

# ==========================================
# 4. PLANTILLAS FALTANTES Y ARREGLADAS
# ==========================================

# 4.1. SIGNUP (Registro de Nuevos Dueños)
signup_html = """{% extends 'salon/base.html' %}
{% block content %}
<div class="row justify-content-center mt-5">
    <div class="col-md-5">
        <div class="card shadow-lg border-0">
            <div class="card-header bg-dark text-white text-center py-3">
                <h4 class="mb-0">🚀 Crear Cuenta de Negocio</h4>
            </div>
            <div class="card-body p-4">
                <form method="post">
                    {% csrf_token %}
                    {{ form.as_p }}
                    <button type="submit" class="btn btn-primary w-100 btn-lg mt-3">Registrarme</button>
                </form>
                <div class="text-center mt-3">
                    <small>¿Ya tienes cuenta? <a href="{% url 'login' %}">Inicia Sesión</a></small>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
"""
write_file(f'{APP_NAME}/templates/registration/signup.html', signup_html)

# 4.2. LANDING SAAS (Arreglando enlaces)
landing_saas_html = """{% extends 'salon/base.html' %}
{% block content %}
<style>
    .hero-section { text-align: center; padding: 100px 20px; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: white; border-radius: 0 0 50px 50px; margin-top: -20px; }
    .hero-title { font-size: 3.5rem; font-weight: 800; margin-bottom: 20px; }
    .cta-button { background: #ec4899; color: white; padding: 15px 40px; border-radius: 50px; font-weight: bold; font-size: 1.2rem; text-decoration: none; display: inline-block; transition: all 0.3s; }
    .cta-button:hover { transform: scale(1.05); color: white; box-shadow: 0 15px 30px rgba(236, 72, 153, 0.5); }
    .feature-card { background: white; padding: 30px; border-radius: 20px; height: 100%; border: 1px solid #f1f5f9; box-shadow: 0 10px 30px rgba(0,0,0,0.05); }
</style>

<div class="hero-section">
    <h1 class="hero-title">Automatiza tu Salón con PASO</h1>
    <p class="lead mb-5 opacity-75">Gestiona citas, inventario y nómina en un solo lugar.</p>
    <a href="{% url 'signup' %}" class="cta-button">¡Prueba Gratis 15 Días!</a>
    <p class="mt-3 small opacity-50">No requiere tarjeta de crédito</p>
</div>

<div class="container mt-5 mb-5">
    <div class="row g-4">
        <div class="col-md-4"><div class="feature-card text-center"><h1>📅</h1><h3>Agenda</h3><p>Reservas automáticas 24/7.</p></div></div>
        <div class="col-md-4"><div class="feature-card text-center"><h1>💰</h1><h3>Pagos</h3><p>Control de caja y comisiones.</p></div></div>
        <div class="col-md-4"><div class="feature-card text-center"><h1>📦</h1><h3>Inventario</h3><p>Control de stock en tiempo real.</p></div></div>
    </div>
</div>

<div class="text-center py-5 bg-light rounded-4">
    <h4>¿Ya tienes cuenta?</h4>
    <a href="{% url 'login' %}" class="btn btn-outline-dark btn-lg mt-3">Iniciar Sesión</a>
</div>
{% endblock %}
"""
write_file(f'{APP_NAME}/templates/salon/landing_saas.html', landing_saas_html)

# 4.3. INVENTORY LIST (Faltaba)
inventory_html = """{% extends 'salon/base.html' %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4 mt-4">
    <h2>📦 Inventario</h2>
    <a href="{% url 'add_product' %}" class="btn btn-success"><i class="fas fa-plus"></i> Nuevo Producto</a>
</div>
<div class="card shadow-sm">
    <div class="card-body p-0">
        <table class="table table-hover mb-0">
            <thead class="table-light"><tr><th>Producto</th><th>Precio</th><th>Stock</th></tr></thead>
            <tbody>
                {% for p in products %}
                <tr>
                    <td>{{ p.name }}</td>
                    <td>${{ p.price }}</td>
                    <td>
                        <span class="badge {% if p.stock < 5 %}bg-danger{% else %}bg-success{% endif %}">
                            {{ p.stock }} un.
                        </span>
                    </td>
                </tr>
                {% empty %}
                <tr><td colspan="3" class="text-center py-4">No hay productos registrados.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
<div class="mt-3"><a href="{% url 'panel_negocio' %}" class="btn btn-secondary">← Volver al Panel</a></div>
{% endblock %}
"""
write_file(f'{APP_NAME}/templates/salon/inventory_list.html', inventory_html)

# 4.4. ADD PRODUCT (Faltaba)
add_product_html = """{% extends 'salon/base.html' %}
{% block content %}
<div class="row justify-content-center mt-4">
    <div class="col-md-6">
        <div class="card shadow">
            <div class="card-header bg-success text-white"><h4>Nuevo Producto</h4></div>
            <div class="card-body">
                <form method="post">
                    {% csrf_token %}
                    <div class="mb-3"><label>Nombre</label><input type="text" name="name" class="form-control" required></div>
                    <div class="mb-3"><label>Precio</label><input type="number" name="price" class="form-control" required></div>
                    <div class="mb-3"><label>Stock Inicial</label><input type="number" name="stock" class="form-control" required></div>
                    <button type="submit" class="btn btn-success w-100">Guardar</button>
                </form>
            </div>
        </div>
        <a href="{% url 'inventory' %}" class="btn btn-link mt-3">Cancelar</a>
    </div>
</div>
{% endblock %}
"""
write_file(f'{APP_NAME}/templates/salon/add_product.html', add_product_html)

# 4.5. SETTINGS (Faltaba)
settings_html = """{% extends 'salon/base.html' %}
{% block content %}
<div class="container mt-4">
    <h2>⚙️ Configuración del Negocio</h2>
    <div class="card mt-3 shadow-sm">
        <div class="card-body">
            <form method="post">
                {% csrf_token %}
                <h5 class="mb-3 text-primary">Pagos Digitales</h5>
                <div class="mb-3">
                    <label>Número Nequi</label>
                    <input type="text" name="nequi" value="{{ tenant.nequi_number }}" class="form-control" placeholder="300...">
                </div>
                <div class="mb-3">
                    <label>API Key Bold (Datafono Virtual)</label>
                    <input type="text" name="bold" value="{{ tenant.bold_api_key }}" class="form-control">
                </div>
                <hr>
                <h5 class="mb-3 text-primary">Redes Sociales</h5>
                <div class="mb-3">
                    <label>Link Instagram</label>
                    <input type="url" name="instagram" value="{{ tenant.instagram }}" class="form-control" placeholder="https://instagram.com/...">
                </div>
                <button type="submit" class="btn btn-primary">Guardar Cambios</button>
            </form>
        </div>
    </div>
    <div class="mt-3"><a href="{% url 'panel_negocio' %}" class="btn btn-secondary">← Volver</a></div>
</div>
{% endblock %}
"""
write_file(f'{APP_NAME}/templates/salon/settings.html', settings_html)

print("--- ✅ REPARACIÓN COMPLETADA ---")
print("1. Se ha corregido la carpeta 'core' a 'salon'.")
print("2. Se añadieron las plantillas faltantes (Inventario, Configuración, Signup).")
print("3. Se arreglaron los enlaces de la Landing Page.")
print("4. Ahora ejecuta: python manage.py migrate")
print("5. Y corre el servidor: python manage.py runserver")
"""

with open('reparar_absoluto.py', 'w', encoding='utf-8') as f:
    f.write(script_content)

print("Script 'reparar_absoluto.py' generado exitosamente.")
