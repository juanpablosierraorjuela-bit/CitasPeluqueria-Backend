from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms
# Eliminamos HorarioEmpleado de la importación porque ya no existe
from .models import Peluqueria, Servicio, Empleado, Cita, PerfilUsuario, Ausencia, SolicitudSaaS

# Eliminamos la clase HorarioInline porque dependía del modelo borrado

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
            form.base_fields['peluqueria'].widget = forms.HiddenInput()
        return form

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and hasattr(request.user, 'perfil'):
            obj.peluqueria = request.user.perfil.peluqueria
        super().save_model(request, obj, form, change)

@admin.register(Empleado)
class EmpleadoAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'apellido')
    # Eliminamos inlines = [HorarioInline] para evitar el error
    exclude = ('peluqueria',)

@admin.register(Servicio)
class ServicioAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'precio')
    exclude = ('peluqueria',)

@admin.register(Cita)
class CitaAdmin(SalonOwnerAdmin):
    list_display = ('cliente_nombre', 'fecha_hora_inicio', 'estado')
    exclude = ('peluqueria',)

@admin.register(SolicitudSaaS)
class SolicitudSaaSAdmin(admin.ModelAdmin):
    list_display = ('nombre_empresa', 'fecha_solicitud')

class CustomUserAdmin(BaseUserAdmin):
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'groups' in form.base_fields: form.base_fields['groups'].widget = forms.CheckboxSelectMultiple()
        if 'user_permissions' in form.base_fields: form.base_fields['user_permissions'].widget = forms.CheckboxSelectMultiple()
        return form

# CRÍTICO: Registros de Peluqueria, PerfilUsuario y Ausencia con filtros de seguridad
@admin.register(Peluqueria)
class PeluqueriaAdmin(SalonOwnerAdmin):
    list_display = ('nombre_visible', 'ciudad', 'telefono')
    exclude = ('slug',)

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(SalonOwnerAdmin):
    list_display = ('user', 'peluqueria', 'es_dueño')

@admin.register(Ausencia)
class AusenciaAdmin(SalonOwnerAdmin):
    list_display = ('empleado', 'fecha_inicio', 'fecha_fin')


admin.site.unregister(User)
admin.site.unregister(Group)
admin.site.register(User, CustomUserAdmin)
admin.site.register(Group)
# Se eliminan los registros simples y se usan los decoradores @admin.register de arriba:
# admin.site.register(Peluqueria)
# admin.site.register(PerfilUsuario)
# admin.site.register(Ausencia)
