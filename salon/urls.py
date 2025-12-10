# UBICACIÓN: salon/urls.py
from django.urls import path
from . import views
from . import api

urlpatterns = [
    # --- PÚBLICO GENERAL ---
    path('', views.inicio, name='inicio'),
    path('negocios/', views.landing_saas, name='landing_saas'),
    
    # --- AUTENTICACIÓN Y REGISTRO ---
    path('ingresar/', views.login_custom, name='login_custom'),
    path('salir/', views.logout_view, name='logout_usuario'),
    # Esta es la ruta mágica para que los empleados se registren solos:
    path('<slug:slug_peluqueria>/unirse-al-equipo/', views.registro_empleado_publico, name='registro_empleado_publico'),

    # --- PANEL DUEÑO (HTML INDEPENDIENTE) ---
    path('negocio/dashboard/', views.panel_negocio, name='panel_negocio'),
    path('negocio/configuracion/', views.configuracion_negocio, name='config_negocio'),
    path('negocio/servicios/', views.gestionar_servicios, name='gestionar_servicios'),
    path('negocio/servicios/borrar/<int:servicio_id>/', views.eliminar_servicio, name='eliminar_servicio'),
    path('negocio/equipo/', views.gestionar_equipo, name='gestionar_equipo'),

    # --- PANEL EMPLEADO (AGENDA) ---
    path('mi-agenda/', views.mi_agenda, name='mi_agenda'),

    # --- RESERVAS (CLIENTE FINAL) ---
    path('<slug:slug_peluqueria>/reservar/', views.agendar_cita, name='agendar_cita'),
    path('<slug:slug_peluqueria>/confirmacion/<int:cita_id>/', views.confirmacion_cita, name='confirmacion_cita'),
    
    # --- PAGOS ---
    path('retorno-bold/', views.retorno_bold, name='retorno_bold'),

    # --- API (JSON) ---
    path('api/v1/<slug:slug_peluqueria>/servicios/', api.listar_servicios, name='api_servicios'),
    path('api/v1/<slug:slug_peluqueria>/empleados/', api.listar_empleados, name='api_empleados'),
    path('api/v1/<slug:slug_peluqueria>/disponibilidad/', api.consultar_disponibilidad, name='api_disponibilidad'),
    path('api/v1/<slug:slug_peluqueria>/citas/crear/', api.crear_cita_api, name='api_crear_cita'),
    
    # API interna para el frontend de reservas
    path('api/horarios/', views.api_obtener_horarios, name='api_obtener_horarios'),
]
