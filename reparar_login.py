import os

print("--- 🔐 REPARANDO SISTEMA DE LOGIN Y ACCESO 🔐 ---")

# A. ARREGLAR URLS (Agregar rutas de autenticación)
urls_code = """from django.urls import path, include
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Rutas de Autenticación (Login/Logout)
    path('accounts/', include('django.contrib.auth.urls')),
    
    # Rutas del Sistema
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
print("✅ urls.py actualizado con rutas de login.")

# B. CREAR LA PLANTILLA DE LOGIN (Que no existía)
os.makedirs('salon/templates/registration', exist_ok=True)

html_login = """
{% extends 'salon/base.html' %}
{% block content %}
<div class="row justify-content-center mt-5">
    <div class="col-md-4">
        <div class="card shadow">
            <div class="card-header bg-dark text-white text-center">
                <h4>🔐 Iniciar Sesión</h4>
            </div>
            <div class="card-body">
                <form method="post">
                    {% csrf_token %}
                    <div class="mb-3">
                        <label>Usuario</label>
                        <input type="text" name="username" class="form-control" required autofocus>
                    </div>
                    <div class="mb-3">
                        <label>Contraseña</label>
                        <input type="password" name="password" class="form-control" required>
                    </div>
                    <button type="submit" class="btn btn-primary w-100">Entrar</button>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}
"""
with open('salon/templates/registration/login.html', 'w', encoding='utf-8') as f:
    f.write(html_login)
print("✅ Plantilla 'login.html' creada.")

# C. CONFIGURAR SETTINGS (Para que sepa a dónde ir al entrar)
settings_path = 'salon_project/settings.py'
with open(settings_path, 'a', encoding='utf-8') as f:
    f.write("\n# --- CONFIGURACION LOGIN AUTOMATICA ---\n")
    f.write("LOGIN_REDIRECT_URL = 'dashboard'\n")
    f.write("LOGOUT_REDIRECT_URL = 'dashboard'\n")
    f.write("LOGIN_URL = '/accounts/login/'\n")

print("✅ settings.py configurado para redirigir al dashboard.")
print("--- SOLUCIÓN APLICADA ---")
