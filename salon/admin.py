# UBICACIÓN: salon/admin.py
from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms
from .models import Peluqueria, Servicio, Empleado, Cita, PerfilUsuario, Ausencia, SolicitudSaaS, HorarioEmpleado

class SalonOwnerAdmin(admin.ModelAdmin):
    """MixIn para que cada dueño solo vea SUS datos"""
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
            form.base_fields['peluqueria'].required = False
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
    # Ocultamos el campo peluqueria al dueño, él ya sabe que es suya
    exclude = ('peluqueria',) 
    inlines = [HorarioEmpleadoInline]
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user" and not request.user.is_superuser:
            # Solo mostrar usuarios que NO sean staff para asignarlos a empleados
            kwargs["queryset"] = User.objects.filter(is_staff=False, is_superuser=False)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(Servicio)
class ServicioAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'precio', 'str_duracion')
    exclude = ('peluqueria',)

@admin.register(Cita)
class CitaAdmin(SalonOwnerAdmin):
    list_display = ('cliente_nombre', 'fecha_hora_inicio', 'estado', 'empleado', 'precio_total')
    list_filter = ('estado', 'fecha_hora_inicio')
    exclude = ('peluqueria',)

@admin.register(Peluqueria)
class PeluqueriaAdmin(admin.ModelAdmin):
    list_display = ('nombre_visible', 'ciudad', 'telefono')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
            return qs.filter(id=request.user.perfil.peluqueria.id)
        return qs.none()
    
    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser:
            return ('slug', 'bold_api_key', 'bold_integrity_key', 'telegram_token')
        return ()

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('user', 'peluqueria', 'es_dueño')

@admin.register(SolicitudSaaS)
class SolicitudSaaSAdmin(admin.ModelAdmin):
    list_display = ('nombre_empresa', 'fecha_solicitud', 'telefono')

# Gestión de Usuarios Personalizada
admin.site.unregister(User)
admin.site.unregister(Group)

@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        return qs.none() # Dueños gestionan usuarios via "Equipo", no via "Users"

admin.site.register(Group)
