from django.contrib import admin
from .models import Tenant, Professional, Service, Product, Appointment, ExternalPayment

# Registro de modelos en el panel
admin.site.register(Tenant)
admin.site.register(Professional)
admin.site.register(Service)
admin.site.register(Product)
admin.site.register(Appointment)
admin.site.register(ExternalPayment)

# Personalización de títulos del Panel de Administración (Header y Título)
admin.site.site_header = "Administración de Citas Peluquería"
admin.site.site_title = "Panel de Control"
admin.site.index_title = "Bienvenido al Sistema de Gestión"
