from django.urls import path
from . import views

urlpatterns = [
    # --- Landing y Accesos Públicos ---
    path('', views.landing_saas_view, name='landing_negocio'),
    path('negocios/', views.landing_saas_view, name='landing_negocio_alt'),
    path('reservar/<slug:slug>/', views.booking_page, name='agendar_cita'),
    path('confirmacion/<int:cita_id>/', views.confirmation_view, name='confirmacion_reserva'),

    # --- Panel de Gestión (Dueño) ---
    path('panel/', views.dashboard, name='panel_negocio'),
    path('configuracion/', views.settings_view, name='configuracion'),
    path('inventario/', views.inventory_view, name='inventario'),
    path('nuevo-profesional/', views.create_professional_view, name='crear_profesional'),

    # --- Gestión de Agenda y Empleados ---
    path('mi-agenda/', views.client_agenda, name='mi_agenda'),
    path('ausencias/', views.manage_absences, name='mis_ausencias'),
    path('eliminar-ausencia/<int:absence_id>/', views.delete_absence, name='eliminar_ausencia'),

    # --- Pagos Externos ---
    path('pago-externo/<int:pro_id>/', views.pay_external, name='pago_externo'),
    path('invitar-externo/', views.invite_external, name='invitar_externo'),
    
    # --- Crear Negocio (Onboarding) ---
    path('crear-negocio/', views.create_tenant_view, name='crear_negocio'),
]
