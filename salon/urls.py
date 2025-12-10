# UBICACIÓN: salon/urls.py
from django.urls import path
from . import views
from . import api

urlpatterns = [
    # --- PÚBLICO ---
    path('', views.inicio, name='inicio'),
    path('auth/login/', views.login_view, name='login_usuario'),
    path('auth/logout/', views.logout_view, name='logout_usuario'),
    path('<slug:slug_peluqueria>/reservar/', views.agendar_cita, name='agendar_cita'),

    # --- PANEL DUEÑO (SOLO ENTRAN SI TIENEN PERFIL DE DUEÑO) ---
    path('negocio/dashboard/', views.panel_negocio, name='panel_negocio'),
    path('negocio/configuracion/', views.configuracion_negocio, name='config_negocio'),
    path('negocio/servicios/', views.gestionar_servicios, name='gestionar_servicios'),
    path('negocio/servicios/borrar/<int:servicio_id>/', views.eliminar_servicio, name='eliminar_servicio'),
    path('negocio/equipo/', views.gestionar_equipo, name='gestionar_equipo'),

    # --- PANEL EMPLEADO (SOLO ENTRAN SI SON EMPLEADOS) ---
    path('mi-agenda/', views.mi_agenda, name='mi_agenda'),

    # --- API ---
    path('api/v1/<slug:slug_peluqueria>/servicios/', api.listar_servicios, name='api_servicios'),
    # ... resto de tus APIs
]
