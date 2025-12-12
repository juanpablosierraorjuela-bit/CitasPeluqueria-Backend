# UBICACIÓN: salon/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('info/', views.landing_saas, name='landing_saas'),
    path('suscripcion/pago/', views.pago_suscripcion_saas, name='pago_suscripcion_saas'),

    path('login/', views.login_custom, name='login_custom'),
    path('logout/', views.logout_view, name='logout_usuario'),
    
    # Rutas Públicas (Cliente Final)
    path('<slug:slug_peluqueria>/unirse-al-equipo/', views.registro_empleado_publico, name='registro_empleado'),
    path('<slug:slug_peluqueria>/reservar/', views.agendar_cita, name='agendar_cita'),
    
    # --- FLUJO DE PAGO (CORREGIDO) ---
    # 1. Pantalla de revisión (donde ven el resumen)
    path('<slug:slug_peluqueria>/confirmacion/<int:cita_id>/', views.confirmacion_cita, name='confirmacion_cita'),
    # 2. Acción oculta que llama a Bold y genera el link
    path('procesar-pago-bold/<int:cita_id>/', views.procesar_pago_bold, name='procesar_pago_bold'),
    # 3. Retorno cuando pagan
    path('webhooks/bold/', views.retorno_bold, name='retorno_bold'),

    path('api/horarios/', views.api_obtener_horarios, name='api_horarios'),

    # Dueño
    path('negocio/dashboard/', views.panel_negocio, name='panel_negocio'),
    path('negocio/servicios/', views.gestionar_servicios, name='gestionar_servicios'),
    path('negocio/servicios/eliminar/<int:servicio_id>/', views.eliminar_servicio, name='eliminar_servicio'),
    path('negocio/equipo/', views.gestionar_equipo, name='gestionar_equipo'),

    # Empleado
    path('mi-agenda/', views.mi_agenda, name='mi_agenda'),
    path('mi-agenda/ausencias/', views.gestionar_ausencias, name='gestionar_ausencias'),
    path('mi-agenda/ausencias/borrar/<int:ausencia_id>/', views.eliminar_ausencia, name='eliminar_ausencia'),
]
