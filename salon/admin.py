from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms
from .models import (
    Peluqueria, Servicio, Empleado, Cita, PerfilUsuario, 
    Ausencia, SolicitudSaaS, HorarioEmpleado, ConfiguracionPlataforma
)

# --- CONFIGURACIÓN GLOBAL ---
@admin.register(ConfiguracionPlataforma)
class ConfigAdmin(admin.ModelAdmin):
    list_display = ('link_pago_bold', 'precio_mensualidad')
    def has_add_permission(self, request):
        if self.model.objects.count() >= 1:
            return False
        return super().has_add_permission(request)

# --- PERMISOS DE DUEÑOS DE SALÓN ---
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
            form.base_fields['peluqueria'].required = False
        return form

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
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
    def has_add_permission(self, request, obj): return False 

@admin.register(Empleado)
class EmpleadoAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'apellido', 'activo')
    exclude = ('peluqueria',) 
    inlines = [HorarioEmpleadoInline]
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user" and not request.user.is_superuser:
            kwargs["queryset"] = User.objects.filter(is_staff=False, is_superuser=False)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(Servicio)
class ServicioAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'precio', 'duracion') 
    exclude = ('peluqueria',)

@admin.register(Ausencia)
class AusenciaAdmin(SalonOwnerAdmin):
    list_display = ('empleado', 'fecha_inicio', 'fecha_fin')
    exclude = ('peluqueria',)
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser and hasattr(request.user, 'perfil'):
            if db_field.name == "empleado":
                kwargs["queryset"] = Empleado.objects.filter(peluqueria=request.user.perfil.peluqueria)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(Cita)
class CitaAdmin(SalonOwnerAdmin):
    list_display = ('cliente_nombre', 'fecha_hora_inicio', 'estado', 'empleado', 'precio_total')
    list_filter = ('estado', 'fecha_hora_inicio')
    exclude = ('peluqueria',)
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser and hasattr(request.user, 'perfil'):
            peluqueria_actual = request.user.perfil.peluqueria
            if db_field.name == "empleado":
                kwargs["queryset"] = Empleado.objects.filter(peluqueria=peluqueria_actual)
            if db_field.name == "servicio":
                kwargs["queryset"] = Servicio.objects.filter(peluqueria=peluqueria_actual)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(Peluqueria)
class PeluqueriaAdmin(admin.ModelAdmin):
    list_display = ('nombre_visible', 'ciudad', 'telefono', 'fecha_inicio_contrato')
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
            return qs.filter(id=request.user.perfil.peluqueria.id)
        return qs.none()
    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser:
            return ('slug', 'bold_api_key', 'bold_integrity_key', 'telegram_token', 'telegram_chat_id', 'bold_secret_key', 'fecha_inicio_contrato', 'activo_saas')
        return ()

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('user', 'peluqueria', 'es_dueño')
    def has_change_permission(self, request, obj=None): return request.user.is_superuser
    def has_add_permission(self, request): return request.user.is_superuser

@admin.register(SolicitudSaaS)
class SolicitudSaaSAdmin(admin.ModelAdmin):
    list_display = ('nombre_empresa', 'fecha_solicitud', 'telefono')

try: admin.site.unregister(User)
except admin.sites.NotRegistered: pass
try: admin.site.unregister(Group)
except admin.sites.NotRegistered: pass

@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        return qs.none()

admin.site.register(Group)
