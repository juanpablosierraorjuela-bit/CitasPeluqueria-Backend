from django.urls import path, include
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
