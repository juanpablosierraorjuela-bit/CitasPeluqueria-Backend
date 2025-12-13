from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    # Inicio y Búsqueda
    path('', views.inicio, name='inicio'),
    path('info/', views.landing_saas, name='landing_saas'),
    
    # Auth
    path('login/', views.login_custom, name='login_custom'),
    path('logout/', views.logout_view, name='logout_usuario'),
    
    # Pagos SaaS
    path('suscripcion/pago/', views.pago_suscripcion_saas, name='pago_suscripcion_saas'),

    # Cliente Final
    path('<slug:slug_peluqueria>/unirse-al-equipo/', views.registro_empleado_publico, name='registro_empleado'),
    path('<slug:slug_peluqueria>/reservar/', views.agendar_cita, name='agendar_cita'),
    path('<slug:slug_peluqueria>/confirmacion/<int:cita_id>/', views.confirmacion_cita, name='confirmacion_cita'),
    
    # PAGOS BOLD
    path('pagos/procesar/<int:cita_id>/', views.procesar_pago_bold, name='procesar_pago_bold'),
    path('pagos/respuesta-bold/', views.retorno_bold, name='retorno_bold'),
    
    # APIs
    path('api/horarios/', views.api_obtener_horarios, name='api_horarios'),

    # Panel Dueño
    path('negocio/dashboard/', views.panel_negocio, name='panel_negocio'),
    path('negocio/confirmar-pago/<int:cita_id>/', views.confirmar_pago_manual, name='confirmar_pago_manual'), 
    path('negocio/inventario/', views.gestionar_inventario, name='gestionar_inventario'), 
    path('negocio/servicios/', views.gestionar_servicios, name='gestionar_servicios'),
    path('negocio/servicios/eliminar/<int:servicio_id>/', views.eliminar_servicio, name='eliminar_servicio'),
    path('negocio/equipo/', views.gestionar_equipo, name='gestionar_equipo'),

    # Panel Empleado
    path('mi-agenda/', views.mi_agenda, name='mi_agenda'),
    path('mi-agenda/ausencias/', views.gestionar_ausencias, name='gestionar_ausencias'),
    path('mi-agenda/ausencias/borrar/<int:ausencia_id>/', views.eliminar_ausencia, name='eliminar_ausencia'),
]

# --- ESTO ES CRÍTICO PARA VER LOS LOGOS ---
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
