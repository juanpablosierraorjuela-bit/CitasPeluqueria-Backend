# UBICACIÓN: salon/admin.py
from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms
from .models import Peluqueria, Servicio, Empleado, Cita, PerfilUsuario, Ausencia, SolicitudSaaS, HorarioEmpleado

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

class HorarioEmpleadoInline(admin.TabularInline):
    model = HorarioEmpleado
    extra = 0
    can_delete = False
    min_num = 7
    max_num = 7
    fields = ('dia_semana', 'hora_inicio', 'hora_fin', 'almuerzo_inicio', 'almuerzo_fin')
    readonly_fields = ('dia_semana',)
    
    def has_add_permission(self, request, obj):
        return False

@admin.register(Empleado)
class EmpleadoAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'apellido', 'activo')
    exclude = ('peluqueria',)
    inlines = [HorarioEmpleadoInline]

@admin.register(Servicio)
class ServicioAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'precio')
    exclude = ('peluqueria',)

@admin.register(Cita)
class CitaAdmin(SalonOwnerAdmin):
    list_display = ('cliente_nombre', 'fecha_hora_inicio', 'estado', 'empleado')
    exclude = ('peluqueria',)

@admin.register(Ausencia)
class AusenciaAdmin(admin.ModelAdmin):
    list_display = ('empleado', 'fecha_inicio', 'fecha_fin')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
            return qs.filter(empleado__peluqueria=request.user.perfil.peluqueria)
        return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "empleado" and not request.user.is_superuser:
            kwargs["queryset"] = Empleado.objects.filter(peluqueria=request.user.perfil.peluqueria)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(Peluqueria)
class PeluqueriaAdmin(admin.ModelAdmin):
    # AGREGADO AQUÍ: hora_apertura y hora_cierre
    list_display = ('nombre_visible', 'ciudad', 'telefono', 'hora_apertura', 'hora_cierre')
    exclude = ('slug',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
            return qs.filter(id=request.user.perfil.peluqueria.id)
        return qs.none()
    
    def has_add_permission(self, request):
        if not request.user.is_superuser: return False
        return True

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(SalonOwnerAdmin):
    list_display = ('user', 'peluqueria', 'es_dueño')

@admin.register(SolicitudSaaS)
class SolicitudSaaSAdmin(admin.ModelAdmin):
    list_display = ('nombre_empresa', 'fecha_solicitud')

class CustomUserAdmin(BaseUserAdmin):
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'groups' in form.base_fields: form.base_fields['groups'].widget = forms.CheckboxSelectMultiple()
        if 'user_permissions' in form.base_fields: form.base_fields['user_permissions'].widget = forms.CheckboxSelectMultiple()
        return form

admin.site.unregister(User)
admin.site.unregister(Group)
admin.site.register(User, CustomUserAdmin)
admin.site.register(Group)
