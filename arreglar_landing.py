import os

print("--- 🚀 CREANDO LANDING PAGE DE VENTAS Y ARREGLANDO RUTAS 🚀 ---")

# 1. CREAR LA LANDING PAGE (HTML)
# Esta es la página que verán al dar clic en "Soy Dueño"
os.makedirs('salon/templates/salon', exist_ok=True)

html_landing = """
{% extends 'salon/base.html' %}
{% block content %}
<style>
    .hero-section { text-align: center; padding: 80px 20px; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: white; border-radius: 0 0 50px 50px; margin-top: -20px; }
    .hero-title { font-size: 3.5rem; font-weight: 800; margin-bottom: 20px; background: linear-gradient(to right, #fff, #94a3b8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .feature-card { background: white; padding: 30px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); transition: transform 0.3s; height: 100%; border: 1px solid #f1f5f9; }
    .feature-card:hover { transform: translateY(-10px); border-color: #0f172a; }
    .icon-box { font-size: 2.5rem; margin-bottom: 20px; color: #ec4899; }
    .cta-button { background: #ec4899; color: white; padding: 15px 40px; border-radius: 50px; font-weight: bold; font-size: 1.2rem; text-decoration: none; display: inline-block; box-shadow: 0 10px 20px rgba(236, 72, 153, 0.3); transition: all 0.3s; }
    .cta-button:hover { transform: scale(1.05); color: white; box-shadow: 0 15px 30px rgba(236, 72, 153, 0.5); }
    .login-footer { margin-top: 80px; padding: 40px; background: #f8fafc; border-top: 1px solid #e2e8f0; text-align: center; }
</style>

<div class="hero-section">
    <h1 class="hero-title">Automatiza tu Salón con PASO</h1>
    <p class="lead mb-5 text-light opacity-75">Deja de perder tiempo en WhatsApp. <br>Gestiona citas, inventario y nómina en un solo lugar.</p>
    <a href="#" class="cta-button">¡Prueba Gratis 15 Días!</a>
    <p class="mt-3 text-muted small">No requiere tarjeta de crédito</p>
</div>

<div class="container mt-5">
    <div class="row g-4">
        <div class="col-md-4">
            <div class="feature-card text-center">
                <div class="icon-box">📅</div>
                <h3>Agenda Automática</h3>
                <p class="text-muted">Tus clientes reservan solos, 24/7. Tú solo recibes la notificación.</p>
            </div>
        </div>
        <div class="col-md-4">
            <div class="feature-card text-center">
                <div class="icon-box">💰</div>
                <h3>Control de Pagos</h3>
                <p class="text-muted">Calcula comisiones de barberos y controla la caja diaria sin errores.</p>
            </div>
        </div>
        <div class="col-md-4">
            <div class="feature-card text-center">
                <div class="icon-box">📦</div>
                <h3>Inventario Real</h3>
                <p class="text-muted">Sabe exactamente cuánta cera y shampoo te queda en stock.</p>
            </div>
        </div>
    </div>
</div>

<div class="login-footer">
    <h4 class="mb-3">¿Ya eres parte de PASO?</h4>
    <p class="text-muted mb-4">Ingresa a tu panel de control para gestionar tu negocio.</p>
    <a href="{% url 'login' %}" class="btn btn-outline-dark btn-lg px-5">
        <i class="fas fa-sign-in-alt me-2"></i> Iniciar Sesión
    </a>
</div>

{% endblock %}
"""
with open('salon/templates/salon/landing_saas.html', 'w', encoding='utf-8') as f:
    f.write(html_landing)
print("✅ landing_saas.html creada con botón de Login abajo.")


# 2. ARREGLAR URLS.PY (Para que 'landing_saas' NO sea el login, sino la página de ventas)
urls_code = """from django.urls import path, include
from . import views

urlpatterns = [
    # 1. PORTADA PRINCIPAL (Buscador de Salones)
    path('', views.public_home, name='home'),
    
    # 2. LANDING PAGE PARA DUEÑOS (Ventas)
    # Al dar clic en "Soy Dueño", vienes aquí:
    path('negocios/', views.landing_saas_view, name='landing_saas'),
    
    # 3. LOGIN Y PANELES
    path('accounts/', include('django.contrib.auth.urls')), # Login real
    path('dashboard/', views.dashboard, name='panel_negocio'),
    
    # 4. RUTAS DE CLIENTE
    path('reservar/<slug:slug>/', views.booking_page, name='agendar_cita'),
    path('mi-agenda/', views.client_agenda, name='mi_agenda'),

    # 5. HERRAMIENTAS INTERNAS
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
print("✅ urls.py corregido: 'landing_saas' ahora apunta a la página de ventas.")


# 3. ACTUALIZAR VIEWS.PY (Agregar la vista de la landing)
# Leemos el archivo actual y agregamos la función que falta
with open('salon/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

if "def landing_saas_view(request):" not in content:
    new_view = """

# --- VISTA LANDING PAGE (VENTAS) ---
def landing_saas_view(request):
    # Si el usuario ya está logueado y tiene negocio, mejor lo mandamos al dashboard directo
    if request.user.is_authenticated and request.user.tenants.exists():
        return redirect('panel_negocio')
    return render(request, 'salon/landing_saas.html')
"""
    with open('salon/views.py', 'a', encoding='utf-8') as f:
        f.write(new_view)
    print("✅ Vista landing_saas_view agregada a views.py.")
else:
    print("ℹ️ La vista ya existía.")

print("--- REPARACIÓN COMPLETADA ---")
