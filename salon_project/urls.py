from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # Esta línea es CLAVE: dirige el tráfico a salon/urls.py
    path('', include('salon.urls')), 
]