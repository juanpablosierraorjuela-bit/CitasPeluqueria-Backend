from django.urls import path, include
from . import views

urlpatterns = [
    # Portada (Tu Diseño)
    path('', views.public_home, name='home'),
    
    # Enlaces que pide tu HTML:
    path('accounts/login/', views.custom_login, name='landing_saas'), # 'Soy Dueño' va al login
    path('dashboard/', views.dashboard, name='panel_negocio'),        # 'Mi Negocio' va al dashboard
    path('reservar/<slug:slug>/', views.booking_page, name='agendar_cita'), # Clic en tarjeta de peluquería
    path('mi-agenda/', views.client_agenda, name='mi_agenda'),        # 'Mi Agenda' (Cliente)

    # Rutas internas
    path('accounts/', include('django.contrib.auth.urls')),
    path('settings/', views.settings_view, name='settings'),
    path('inventory/', views.inventory_list, name='inventory'),
    path('inventory/add/', views.add_product, name='add_product'),
    path('invite-pro/', views.invite_external, name='invite_external'),
    path('register-external/<uuid:token>/', views.register_external_view, name='register_external'),
    path('pay-pro/<int:pro_id>/', views.pay_external, name='pay_external'),
]
