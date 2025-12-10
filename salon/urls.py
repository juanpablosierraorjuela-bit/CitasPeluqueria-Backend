# UBICACIÓN: salon/urls.py
from django.urls import path
from . import views
from . import api

urlpatterns = [
    # --- PÚBLICO GENERAL ---
    path('', views.inicio, name='inicio'),
    path('negocios/', views.landing_saas, name='landing_saas'),
    
    # --- AUTENTICACIÓN Y ONBOARDING ---
    path('ingresar/', views.login_custom, name='login_custom'),
    path('salir/', views.logout_view, name='logout_usuario'),
    # Ruta mágica para auto-registro de empleados (Link de invitación)
    path('<slug:slug_peluqueria>/unirse-al-equipo/', views.registro_empleado_publico, name='registro_empleado_publico'),

    # --- PANEL DUEÑO (ADMINISTRACIÓN) ---
    path('negocio/dashboard/', views.panel_negocio, name='panel_negocio'),
    path('negocio/configuracion/', views.configuracion_negocio, name='config_negocio'),
    path('negocio/servicios/', views.gestionar_servicios, name='gestionar_servicios'),
    path('negocio/servicios/borrar/<int:servicio_id>/', views.eliminar_servicio, name='eliminar_servicio'),
    path('negocio/equipo/', views.gestionar_equipo, name='gestionar_equipo'),

    # --- PANEL EMPLEADO (AGENDA PERSONAL) ---
    path('mi-agenda/', views.mi_agenda, name='mi_agenda'),

    # --- RESERVAS (CLIENTE FINAL) ---
    # Ruta principal
    path('<slug:slug_peluqueria>/reservar/', views.agendar_cita, name='agendar_cita'),
    # Alias de seguridad (por si usan el link antiguo)
    path('<slug:slug_peluqueria>/agendar/', views.agendar_cita),
    
    path('<slug:slug_peluqueria>/confirmacion/<int:cita_id>/', views.confirmacion_cita, name='confirmacion_cita'),
    
    # --- PAGOS ---
    path('retorno-bold/', views.retorno_bold, name='retorno_bold'),

    # --- API EXTERNA (APP MÓVIL/FLET) ---
    path('api/v1/<slug:slug_peluqueria>/servicios/', api.listar_servicios, name='api_servicios'),
    path('api/v1/<slug:slug_peluqueria>/empleados/', api.listar_empleados, name='api_empleados'),
    path('api/v1/<slug:slug_peluqueria>/disponibilidad/', api.consultar_disponibilidad, name='api_disponibilidad'),
    path('api/v1/<slug:slug_peluqueria>/citas/crear/', api.crear_cita_api, name='api_crear_cita'),
    
    # --- API INTERNA (FRONTEND WEB) ---
    path('api/horarios/', views.api_obtener_horarios, name='api_obtener_horarios'),
]
