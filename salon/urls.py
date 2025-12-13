from django.urls import path, include
from . import views

urlpatterns = [
    # TUS RUTAS BASADAS EN TUS PLANTILLAS:
    path('', views.public_home, name='home'),                            # index.html
    path('negocios/', views.landing_saas_view, name='landing_saas'),     # landing_saas.html
    path('mi-agenda/', views.client_agenda, name='mi_agenda'),           # mi_agenda.html
    path('dashboard/', views.dashboard, name='panel_negocio'),           # dashboard.html
    
    # Rutas de Sistema
    path('accounts/', include('django.contrib.auth.urls')),
    # VISTA CORREGIDA: Apunta a 'agendar'
    path('reservar/<slug:slug>/', views.booking_page, name='agendar'), 
    
    # Herramientas
    path('settings/', views.settings_view, name='settings'),
    path('inventory/', views.inventory_list, name='inventory'),
    path('inventory/add/', views.add_product, name='add_product'),
    path('invite-pro/', views.invite_external, name='invite_external'),
    path('register-external/<uuid:token>/', views.register_external_view, name='register_external'),
    path('pay-pro/<int:pro_id>/', views.pay_external, name='pay_external'),
]
