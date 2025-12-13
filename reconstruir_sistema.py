import os
import sys

print("--- 🚑 INICIANDO RECONSTRUCCIÓN TOTAL DEL SISTEMA (VISUAL + LÓGICO) �� ---")

# A. REPARAR VISTAS (Lógica del Cerebro)
views_code = """from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Tenant, Professional, Service, Product, Appointment, ExternalPayment
from django.contrib import messages
from django.db.models import Sum
from django.contrib.auth.models import User
import uuid

@login_required
def dashboard(request):
    # 1. BUSCAR SI EL USUARIO TIENE NEGOCIO
    tenant = Tenant.objects.filter(users=request.user).first()
    
    # 2. SI NO TIENE NEGOCIO -> MANDARLO A CREARLO (CRÍTICO PARA QUE NO SE ROMPA)
    if not tenant:
        if request.method == 'POST':
            name = request.POST.get('name')
            subdomain = request.POST.get('subdomain')
            try:
                # Crear el negocio
                new_tenant = Tenant.objects.create(name=name, subdomain=subdomain)
                new_tenant.users.add(request.user)
                new_tenant.save()
                messages.success(request, f"¡Bienvenido a tu nuevo panel de {name}!")
                return redirect('dashboard')
            except Exception as e:
                messages.error(request, "Error: El identificador ya existe. Prueba otro.")
        return render(request, 'salon/create_tenant.html')

    # 3. SI YA TIENE NEGOCIO -> CARGAR DATOS
    professionals = Professional.objects.filter(tenant=tenant)
    external_pros = professionals.filter(is_external=True)
    internal_pros = professionals.filter(is_external=False)
    services = Service.objects.filter(tenant=tenant)
    products = Product.objects.filter(tenant=tenant)
    appointments = Appointment.objects.filter(tenant=tenant).order_by('-date')
    
    total_sales = appointments.filter(status='COMPLETED').aggregate(Sum('service__price'))['service__price__sum'] or 0

    context = {
        'tenant': tenant,
        'professionals': professionals,
        'external_pros': external_pros,
        'internal_pros': internal_pros,
        'services': services,
        'products': products,
        'appointments': appointments,
        'total_sales': total_sales,
        'show_inventory': True, # Activa botones en el HTML
        'show_settings': True,
    }
    return render(request, 'salon/dashboard.html', context)

@login_required
def inventory_list(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    if not tenant: return redirect('dashboard')
    products = Product.objects.filter(tenant=tenant)
    return render(request, 'salon/inventory_list.html', {'products': products})

@login_required
def add_product(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    if request.method == 'POST':
        name = request.POST.get('name')
        price = request.POST.get('price')
        stock = request.POST.get('stock')
        Product.objects.create(tenant=tenant, name=name, price=price, stock=stock)
        messages.success(request, 'Producto guardado')
        return redirect('dashboard')
    return render(request, 'salon/add_product.html')

@login_required
def invite_external(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    if request.method == 'POST':
        name = request.POST.get('name')
        commission = request.POST.get('commission')
        # Crear perfil vacio con token
        pro = Professional.objects.create(
            tenant=tenant, name=name, phone="000", is_external=True, commission_rate=commission
        )
        domain = request.build_absolute_uri('/')[:-1]
        link = f"{domain}/register-external/{pro.invite_token}/"
        messages.success(request, f"LINK CREADO: {link}")
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
        
        messages.success(request, "Registro Exitoso. Accede al sistema.")
        return redirect('dashboard') # O login
        
    return render(request, 'salon/register_external.html', {'pro': pro})

@login_required
def pay_external(request, pro_id):
    pro = get_object_or_404(Professional, id=pro_id)
    if request.method == 'POST':
        amount = float(request.POST.get('amount'))
        ExternalPayment.objects.create(professional=pro, amount=amount)
        pro.balance_due = float(pro.balance_due) - amount
        pro.save()
        messages.success(request, "Pago registrado")
    return redirect('dashboard')

@login_required
def settings_view(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    if request.method == 'POST':
        tenant.nequi_number = request.POST.get('nequi')
        tenant.bold_api_key = request.POST.get('bold')
        tenant.save()
        messages.success(request, "Ajustes Guardados")
    return render(request, 'salon/settings.html', {'tenant': tenant})
"""
with open('salon/views.py', 'w', encoding='utf-8') as f:
    f.write(views_code)
print("✅ views.py reconstruido.")

# B. REPARAR URLS (El Mapa)
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
with open('salon/urls.py', 'w', encoding='utf-8') as f:
    f.write(urls_code)
print("✅ urls.py reconstruido.")

# C. REPARAR PLANTILLAS HTML (Lo que no ves)
os.makedirs('salon/templates/salon', exist_ok=True)

# 1. Base HTML (Estructura común)
html_base = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Panel de Gestión</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
</head>
<body class="bg-light">
    <nav class="navbar navbar-dark bg-dark mb-4">
        <div class="container-fluid">
            <a class="navbar-brand" href="{% url 'dashboard' %}">💈 Gestión Salón</a>
            {% if user.is_authenticated %}
            <span class="text-white">Hola, {{ user.username }}</span>
            {% endif %}
        </div>
    </nav>
    <div class="container">
        {% if messages %}
            {% for message in messages %}
                <div class="alert alert-{{ message.tags }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
        {% block content %}{% endblock %}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""
with open('salon/templates/salon/base.html', 'w', encoding='utf-8') as f:
    f.write(html_base)

# 2. Pantalla de Crear Negocio (LA QUE FALTABA)
html_create = """
{% extends 'salon/base.html' %}
{% block content %}
<div class="row justify-content-center mt-5">
    <div class="col-md-6">
        <div class="card shadow-lg">
            <div class="card-header bg-primary text-white text-center">
                <h3>🚀 Inicia tu Negocio</h3>
            </div>
            <div class="card-body p-4">
                <p class="text-center text-muted">Aún no tienes un salón registrado. Crea uno para comenzar.</p>
                <form method="POST">
                    {% csrf_token %}
                    <div class="mb-3">
                        <label class="form-label">Nombre del Negocio</label>
                        <input type="text" name="name" class="form-control" placeholder="Ej: Barbería Styles" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Identificador (URL)</label>
                        <input type="text" name="subdomain" class="form-control" placeholder="Ej: styles-bogota" required>
                        <small class="text-muted">Sin espacios ni tildes.</small>
                    </div>
                    <button type="submit" class="btn btn-success w-100 btn-lg">Crear Panel</button>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}
"""
with open('salon/templates/salon/create_tenant.html', 'w', encoding='utf-8') as f:
    f.write(html_create)

# 3. Dashboard Principal (Completo)
html_dashboard = """
{% extends 'salon/base.html' %}
{% block content %}
<div class="row mb-4">
    <div class="col-md-8">
        <h1>{{ tenant.name }} <span class="badge bg-secondary">Admin</span></h1>
    </div>
    <div class="col-md-4 text-end">
        <a href="{% url 'settings' %}" class="btn btn-outline-secondary"><i class="fas fa-cog"></i> Configurar</a>
    </div>
</div>

<div class="row mb-4">
    <div class="col-md-4">
        <div class="card text-white bg-success mb-3">
            <div class="card-body">
                <h5 class="card-title">Ventas Totales</h5>
                <p class="card-text display-6">${{ total_sales }}</p>
            </div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card text-white bg-info mb-3">
            <div class="card-body">
                <h5 class="card-title">Citas</h5>
                <p class="card-text display-6">{{ appointments.count }}</p>
            </div>
        </div>
    </div>
</div>

<div class="card mb-4 shadow-sm">
    <div class="card-header bg-warning text-dark d-flex justify-content-between align-items-center">
        <h5 class="mb-0"><i class="fas fa-motorcycle"></i> Domiciliarios Externos</h5>
        <button class="btn btn-sm btn-dark" data-bs-toggle="modal" data-bs-target="#inviteModal">
            <i class="fas fa-plus"></i> Invitar Nuevo
        </button>
    </div>
    <div class="card-body">
        {% if external_pros %}
        <div class="table-responsive">
            <table class="table table-hover">
                <thead><tr><th>Nombre</th><th>Comisión Dueño</th><th>Saldo Pendiente</th><th>Acción</th></tr></thead>
                <tbody>
                {% for pro in external_pros %}
                <tr>
                    <td>{{ pro.name }}</td>
                    <td>{{ pro.commission_rate }}%</td>
                    <td class="text-danger fw-bold">${{ pro.balance_due }}</td>
                    <td>
                        <form action="{% url 'pay_external' pro.id %}" method="POST" class="d-flex gap-2">
                            {% csrf_token %}
                            <input type="number" name="amount" class="form-control form-control-sm" placeholder="Monto a pagar" style="width: 100px;">
                            <button type="submit" class="btn btn-sm btn-success">Pagar</button>
                        </form>
                    </td>
                </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
            <p class="text-muted">No tienes domiciliarios registrados.</p>
        {% endif %}
    </div>
</div>

<div class="card mb-4 shadow-sm">
    <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center">
        <h5 class="mb-0"><i class="fas fa-boxes"></i> Inventario</h5>
        <a href="{% url 'inventory' %}" class="btn btn-sm btn-light">Ver Todo</a>
    </div>
    <div class="card-body">
        <form action="{% url 'add_product' %}" method="POST" class="row g-3">
            {% csrf_token %}
            <div class="col-md-4"><input type="text" name="name" class="form-control" placeholder="Producto" required></div>
            <div class="col-md-3"><input type="number" name="price" class="form-control" placeholder="Precio" required></div>
            <div class="col-md-3"><input type="number" name="stock" class="form-control" placeholder="Stock" required></div>
            <div class="col-md-2"><button type="submit" class="btn btn-primary w-100">Añadir</button></div>
        </form>
        <hr>
        <ul class="list-group">
        {% for p in products|slice:":5" %}
            <li class="list-group-item d-flex justify-content-between align-items-center">
                {{ p.name }}
                <span class="badge bg-primary rounded-pill">{{ p.stock }} un.</span>
            </li>
        {% endfor %}
        </ul>
    </div>
</div>

<div class="modal fade" id="inviteModal" tabindex="-1">
    <div class="modal-dialog">
        <form class="modal-content" method="POST" action="{% url 'invite_external' %}">
            {% csrf_token %}
            <div class="modal-header">
                <h5 class="modal-title">Invitar Domiciliario</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <label>Nombre del Profesional</label>
                <input type="text" name="name" class="form-control mb-3" required>
                <label>Comisión que cobras tú (Dueño) %</label>
                <input type="number" name="commission" class="form-control" value="20" required>
            </div>
            <div class="modal-footer">
                <button type="submit" class="btn btn-primary">Generar Link</button>
            </div>
        </form>
    </div>
</div>
{% endblock %}
"""
with open('salon/templates/salon/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html_dashboard)

print("✅ Todas las plantillas HTML creadas.")
print("--- PROCESO COMPLETADO ---")
