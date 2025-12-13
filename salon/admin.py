from django.contrib import admin
from .models import Tenant, Professional, Service, Product, Appointment, ExternalPayment
admin.site.register(Professional)
admin.site.register(Tenant)
admin.site.register(Service)
admin.site.register(Product)
admin.site.register(Appointment)
admin.site.register(ExternalPayment)
