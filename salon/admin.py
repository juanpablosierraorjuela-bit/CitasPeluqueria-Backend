from django.contrib import admin
from .models import Tenant, Professional, Service, Product, Appointment, ExternalPayment, Absence

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('name', 'subdomain', 'ciudad', 'user')
    search_fields = ('name', 'ciudad')

@admin.register(Professional)
class ProfessionalAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tenant', 'especialidad')
    list_filter = ('tenant',)

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio', 'duracion', 'tenant')
    list_filter = ('tenant',)

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('cliente_nombre', 'fecha_hora_inicio', 'servicio', 'empleado', 'estado')
    list_filter = ('estado', 'fecha_hora_inicio')

admin.site.register(Product)
admin.site.register(ExternalPayment)
admin.site.register(Absence)
