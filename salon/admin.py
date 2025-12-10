# UBICACIÓN: salon/admin.py
from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms
from .models import Peluqueria, Servicio, Empleado, Cita, PerfilUsuario, Ausencia, SolicitudSaaS

# 1. CLASE BASE (El Guardia General)
class SalonOwnerAdmin(admin.ModelAdmin):
    """
    Este 'Guardia' se encarga de que cada dueño solo vea SUS datos.
    Se usa para modelos que tienen un campo directo 'peluqueria'.
    """
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        # Si es dueño, filtramos por su peluquería
        if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
            return qs.filter(peluqueria=request.user.perfil.peluqueria)
        return qs.none()
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Ocultamos el campo peluquería para que no lo puedan cambiar
        if not request.user.is_superuser and 'peluqueria' in form.base_fields:
            form.base_fields['peluqueria'].widget = forms.HiddenInput()
        return form

    def save_model(self, request, obj, form, change):
        # Asignamos la peluquería automáticamente al guardar
        if not request.user.is_superuser and hasattr(request.user, 'perfil'):
            obj.peluqueria = request.user.perfil.peluqueria
        super().save_model(request, obj, form, change)

# 2. MODELOS ESTÁNDAR (Tienen campo 'peluqueria', usan el Guardia normal)
@admin.register(Servicio)
class ServicioAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'precio', 'duracion')
    exclude = ('peluqueria',)

@admin.register(Cita)
class CitaAdmin(SalonOwnerAdmin):
    list_display = ('cliente_nombre', 'fecha_hora_inicio', 'estado', 'empleado')
    exclude = ('peluqueria',)

@admin.register(Empleado)
class EmpleadoAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'apellido', 'activo')
    exclude = ('peluqueria',)

# 3. CASOS ESPECIALES (Aquí estaba el Error 500)

@admin.register(Ausencia)
class AusenciaAdmin(admin.ModelAdmin):
    """
    CORREGIDO: Ausencia no tiene campo 'peluqueria', la tiene su 'empleado'.
    Por eso usamos un filtro especial: empleado__peluqueria
    """
    list_display = ('empleado', 'fecha_inicio', 'fecha_fin')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
            # MAGIA AQUÍ: Filtramos a través del empleado
            return qs.filter(empleado__peluqueria=request.user.perfil.peluqueria)
        return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Al crear ausencia, solo mostrar empleados de MI peluquería
        if db_field.name == "empleado" and not request.user.is_superuser:
            kwargs["queryset"] = Empleado.objects.filter(peluqueria=request.user.perfil.peluqueria)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(Peluqueria)
class PeluqueriaAdmin(admin.ModelAdmin):
    """
    CORREGIDO: Peluqueria no tiene campo 'peluqueria' (es ella misma).
    Filtramos por ID.
    """
    list_display = ('nombre_visible', 'ciudad', 'telefono')
    exclude = ('slug',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
            # MAGIA AQUÍ: Filtramos por el ID de la peluquería del usuario
            return qs.filter(id=request.user.perfil.peluqueria.id)
        return qs.none()
    
    def has_add_permission(self, request):
        # Un dueño no puede crear nuevas peluquerías, solo editar la suya
        if not request.user.is_superuser: return False
        return True

# 4. CONFIGURACIÓN DE USUARIOS
@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(SalonOwnerAdmin):
    list_display = ('user', 'peluqueria', 'es_dueño')

@admin.register(SolicitudSaaS)
class SolicitudSaaSAdmin(admin.ModelAdmin):
    list_display = ('nombre_empresa', 'fecha_solicitud')

# Re-registro de User para mejorar la interfaz
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
