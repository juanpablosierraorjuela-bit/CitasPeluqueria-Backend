from django.urls import path
from . import views
from . import api  

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('dashboard/', views.dashboard_dueño, name='dashboard_dueño'),
    path('cita-confirmada/', views.cita_confirmada, name='cita_confirmada'),
    path('<slug:slug_peluqueria>/agendar/', views.agendar_cita, name='agendar_cita'),
    path('retorno-bold/', views.retorno_bold, name='retorno_bold'), # <--- ESTA ES LA CLAVE
    path('manifest.json', views.manifest_view, name='pwa_manifest'),

    # API
    path('api/horarios/', views.obtener_horas_disponibles, name='api_horarios_web'),
    path('api/v1/<slug:slug_peluqueria>/servicios/', api.listar_servicios, name='api_servicios'),
    path('api/v1/<slug:slug_peluqueria>/empleados/', api.listar_empleados, name='api_empleados'),
    path('api/v1/<slug:slug_peluqueria>/disponibilidad/', api.consultar_disponibilidad, name='api_disponibilidad'),
    path('api/v1/<slug:slug_peluqueria>/citas/crear/', api.crear_cita_api, name='api_crear_cita'),
]
