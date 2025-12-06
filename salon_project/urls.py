from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # 1. Ruta para el panel de administración
    path('admin/', admin.site.urls),
    
    # 2. RUTA CLAVE: Incluye todas las rutas de la aplicación 'salon' en la raíz del proyecto.
    path('', include('salon.urls')), 
]