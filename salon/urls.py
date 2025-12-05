from django.urls import path
from . import views

urlpatterns = [
    # 1. RUTA DE INICIO (La Portada General)
    # Esta ruta vacía '' atrapa cuando entras a http://127.0.0.1:8000/
    path('', views.inicio, name='inicio'),

    # 2. API DE HORARIOS (¡NUEVA E IMPORTANTE!)
    # Esta es la ruta oculta que usa el JavaScript para preguntar qué horas están libres.
    # Sin esto, el calendario no cargará los botones de hora.
    path('api/horarios/', views.obtener_horas_disponibles, name='api_horarios'),

    # 3. RUTA DE ÉXITO
    # A donde llega el usuario después de pedir la cita exitosamente
    path('cita-confirmada/', views.cita_confirmada, name='cita_confirmada'),

    # 4. RUTA DINÁMICA POR PELUQUERÍA
    # Detecta el nombre (slug) de la peluquería en la URL
    # Ejemplo: /mi-salon/agendar/ o /tierradereina/agendar/
    path('<slug:slug_peluqueria>/agendar/', views.agendar_cita, name='agendar_cita'),
]