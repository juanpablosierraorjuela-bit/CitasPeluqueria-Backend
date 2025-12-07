from django.urls import path
from . import views
from . import api  # <--- IMPORTANTE: Importamos el archivo api.py que creamos en el Paso 2

urlpatterns = [
    # VISTAS WEB (Para humanos)
    path('', views.inicio, name='inicio'),
    path('cita-confirmada/', views.cita_confirmada, name='cita_confirmada'),
    path('<slug:slug_peluqueria>/agendar/', views.agendar_cita, name='agendar_cita'),
    
    # API INTERNA (Para el JavaScript del sitio web)
    path('api/horarios/', views.obtener_horas_disponibles, name='api_horarios_web'),

    # API EXTERNA (Para tu App Flet / Celulares)
    # Fíjate que ahora todas incluyen <slug_peluqueria> para saber a qué negocio preguntar
    path('api/v1/<slug:slug_peluqueria>/servicios/', api.listar_servicios, name='api_servicios'),
    path('api/v1/<slug:slug_peluqueria>/empleados/', api.listar_empleados, name='api_empleados'),
    path('api/v1/<slug:slug_peluqueria>/disponibilidad/', api.consultar_disponibilidad, name='api_disponibilidad'),
    path('api/v1/<slug:slug_peluqueria>/citas/crear/', api.crear_cita_api, name='api_crear_cita'),
]