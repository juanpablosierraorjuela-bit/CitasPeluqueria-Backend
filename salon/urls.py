from django.urls import path
from . import views

urlpatterns = [
    # --- PÁGINA DE INICIO ---
    path('', views.inicio, name='inicio'),
    
    # --- RUTA FALTANTE QUE CAUSABA EL ERROR 500 ---
    path('info/', views.landing_saas, name='landing_saas'),

    # --- AUTENTICACIÓN ---
    path('login/', views.login_custom, name='login_custom'),
    path('logout/', views.logout_view, name='logout_usuario'),
    
    # --- RUTAS PUBLICAS ---
    path('<slug:slug_peluqueria>/unirse-al-equipo/', views.registro_empleado_publico, name='registro_empleado'),
    path('<slug:slug_peluqueria>/reservar/', views.agendar_cita, name='agendar_cita'),
    path('<slug:slug_peluqueria>/confirmacion/<int:cita_id>/', views.confirmacion_cita, name='confirmacion_cita'),

    # --- API ---
    path('api/horarios/', views.api_obtener_horarios, name='api_horarios'),
    path('webhooks/bold/', views.retorno_bold, name='retorno_bold'),

    # --- PANEL DE CONTROL (DUEÑO) ---
    path('negocio/dashboard/', views.panel_negocio, name='panel_negocio'),
    path('negocio/configuracion/', views.configuracion_negocio, name='config_negocio'),
    path('negocio/servicios/', views.gestionar_servicios, name='gestionar_servicios'),
    path('negocio/servicios/eliminar/<int:servicio_id>/', views.eliminar_servicio, name='eliminar_servicio'),
    path('negocio/equipo/', views.gestionar_equipo, name='gestionar_equipo'),

    # --- PANEL EMPLEADO ---
    path('mi-agenda/', views.mi_agenda, name='mi_agenda'),
]
