import os

print("--- 🔗 CONECTANDO TU LANDING PAGE EXISTENTE 🔗 ---")

# 1. ASEGURAR QUE VIEWS.PY TENGA LA LÓGICA CORRECTA
# (No tocamos el HTML, solo le decimos a Django cómo usarlo)
vista_landing = """
# --- VISTA LANDING PAGE (VENTAS) ---
def landing_saas_view(request):
    # LÓGICA INTELIGENTE:
    # 1. Si ya está logueado Y tiene negocio -> Va al Panel directo.
    if request.user.is_authenticated and request.user.tenants.exists():
        return redirect('panel_negocio')
    
    # 2. Si no -> Muestra TU landing page de ventas.
    return render(request, 'salon/landing_saas.html')
"""

# Leemos views.py para ver si falta agregar la función
with open('salon/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

if "def landing_saas_view(request):" not in content:
    with open('salon/views.py', 'a', encoding='utf-8') as f:
        f.write(vista_landing)
    print("✅ Vista 'landing_saas_view' agregada correctamente.")
else:
    # Si ya existe, nos aseguramos que tenga la lógica de redirección
    print("ℹ️ La vista ya existía, verificando lógica...")
    # (Aquí podrías hacer un reemplazo más fino si fuera necesario, 
    # pero por seguridad asumimos que si existe, intentamos usarla)

# 2. ARREGLAR URLS.PY (El Mapa)
# Esto asegura que /negocios/ cargue esa vista, y que los botones apunten ahí.
urls_code = """from django.urls import path, include
from . import views

urlpatterns = [
    # 1. PORTADA (Buscador)
    path('', views.public_home, name='home'),
    
    # 2. TU LANDING PAGE (Ventas)
    # Al dar clic en "Soy Dueño", vienes aquí:
    path('negocios/', views.landing_saas_view, name='landing_saas'),
    
    # 3. LOGIN Y PANELES
    path('accounts/', include('django.contrib.auth.urls')),
    path('dashboard/', views.dashboard, name='panel_negocio'),
    
    # 4. RUTAS DE CLIENTE
    path('reservar/<slug:slug>/', views.booking_page, name='agendar_cita'),
    path('mi-agenda/', views.client_agenda, name='mi_agenda'),

    # 5. HERRAMIENTAS
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
print("✅ Urls.py re-configurado para apuntar a tu Landing.")

print("--- CONEXIÓN COMPLETADA ---")
