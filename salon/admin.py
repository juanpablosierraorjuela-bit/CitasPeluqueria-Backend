from django.contrib import admin, messages
from django.contrib.auth.models import Group, User 
from django.urls import path, reverse 
from django.http import HttpResponseRedirect 
from django.utils.safestring import mark_safe 
import requests 
from .models import (
    Peluqueria, Servicio, Empleado, HorarioSemanal, Cita, PerfilUsuario, Ausencia
)

class SalonOwnerAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
            return qs.filter(peluqueria=request.user.perfil.peluqueria)
        return qs.none()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser and 'peluqueria' in form.base_fields:
            del form.base_fields['peluqueria'] 
        return form

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
                obj.peluqueria = request.user.perfil.peluqueria
        super().save_model(request, obj, form, change)

class SuperuserOnlyAdmin(admin.ModelAdmin):
    def has_module_permission(self, request): return request.user.is_superuser
    
@admin.register(Peluqueria)
class PeluqueriaAdmin(SuperuserOnlyAdmin):
    list_display = ('nombre', 'slug', 'bold_status')
    prepopulated_fields = {'slug': ('nombre',)}
    
    @admin.display(description='Pasarela Bold')
    def bold_status(self, obj):
        if obj.bold_api_key: return "✅ Activa"
        return "❌ Inactiva"

@admin.register(Servicio)
class ServicioAdmin(SalonOwnerAdmin):
    # AQUÍ MOSTRAMOS LA DURACIÓN FORMATEADA
    list_display = ('nombre', 'precio', 'str_duracion')
    exclude = ('peluqueria',)

@admin.register(Empleado)
class EmpleadoAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'apellido')
    exclude = ('peluqueria',)

@admin.register(Cita)
class CitaAdmin(SalonOwnerAdmin):
    list_display = ('cliente_nombre', 'empleado', 'fecha_hora_inicio', 'estado', 'pago_info') 
    filter_horizontal = ('servicios',) 
    exclude = ('peluqueria',) 
    
    @admin.display(description='Pago Bold')
    def pago_info(self, obj):
        if obj.abono_pagado > 0: return f"${obj.abono_pagado}"
        return "-"

@admin.register(Ausencia)
class AusenciaAdmin(SalonOwnerAdmin): 
    list_display = ('empleado', 'fecha_inicio', 'fecha_fin', 'motivo')

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(SuperuserOnlyAdmin):
    list_display = ('user', 'peluqueria')

admin.site.unregister(User)
admin.site.unregister(Group)
admin.site.register(User)
admin.site.register(Group)
