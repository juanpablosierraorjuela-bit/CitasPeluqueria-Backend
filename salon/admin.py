# UBICACIÓN: salon/admin.py
from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms
from .models import (
    Peluqueria, Servicio, Empleado, Cita, PerfilUsuario, 
    Ausencia, SolicitudSaaS, HorarioEmpleado
)

class SalonOwnerAdmin(admin.ModelAdmin):
    """
    MixIn Maestro: Asegura que el usuario logueado (si es Dueño)
    solo pueda ver, editar y asignar datos de SU propia peluquería.
    """
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Si tiene perfil y peluquería asignada, filtramos
        if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
            return qs.filter(peluqueria=request.user.perfil.peluqueria)
        return qs.none() # Si no es dueño ni admin, no ve nada
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Ocultamos el campo 'peluqueria' para que no lo puedan cambiar
        if not request.user.is_superuser and 'peluqueria' in form.base_fields:
            form.base_fields['peluqueria'].widget = forms.HiddenInput()
            form.base_fields['peluqueria'].required = False
        return form

    def save_model(self, request, obj, form, change):
        # Al guardar, asignamos automáticamente la peluquería del dueño
        if not request.user.is_superuser and hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
            obj.peluqueria = request.user.perfil.peluqueria
        super().save_model(request, obj, form, change)

# --- INLINES ---

class HorarioEmpleadoInline(admin.TabularInline):
    model = HorarioEmpleado
    extra = 0
    can_delete = False
    min_num = 7
    max_num = 7
    fields = ('dia_semana', 'hora_inicio', 'hora_fin', 'almuerzo_inicio', 'almuerzo_fin')
    readonly_fields = ('dia_semana',)
    
    def has_add_permission(self, request, obj):
        return False # Evita botón "Agregar otro", ya que son fijos 7 días

# --- MODEL ADMINS ---

@admin.register(Empleado)
class EmpleadoAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'apellido', 'activo')
    exclude = ('peluqueria',) 
    inlines = [HorarioEmpleadoInline]
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Filtro para que al asignar un Usuario al Empleado, solo salgan usuarios disponibles
        if db_field.name == "user" and not request.user.is_superuser:
            kwargs["queryset"] = User.objects.filter(is_staff=False, is_superuser=False)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(Servicio)
class ServicioAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'precio', 'duracion') # Asegúrate que en models sea 'duracion' o 'str_duracion' si es property
    exclude = ('peluqueria',)

@admin.register(Ausencia)
class AusenciaAdmin(SalonOwnerAdmin):
    list_display = ('empleado', 'fecha_inicio', 'fecha_fin', 'tipo')
    exclude = ('peluqueria',)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Al crear ausencia, solo mostrar MIS empleados
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
        # SEGURIDAD CRÍTICA: Filtrar dropdowns dentro de la Cita
        if not request.user.is_superuser and hasattr(request.user, 'perfil'):
            peluqueria_actual = request.user.perfil.peluqueria
            
            if db_field.name == "empleado":
                kwargs["queryset"] = Empleado.objects.filter(peluqueria=peluqueria_actual)
            
            if db_field.name == "servicio":
                kwargs["queryset"] = Servicio.objects.filter(peluqueria=peluqueria_actual)
                
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

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
        # Protegemos datos sensibles de API Keys para que el dueño no los rompa
        if not request.user.is_superuser:
            return ('slug', 'bold_api_key', 'bold_integrity_key', 'telegram_token')
        return ()

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('user', 'peluqueria', 'es_dueño')
    # Idealmente, solo el SuperAdmin debería tocar esto para asignar dueños
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    def has_add_permission(self, request):
        return request.user.is_superuser

@admin.register(SolicitudSaaS)
class SolicitudSaaSAdmin(admin.ModelAdmin):
    list_display = ('nombre_empresa', 'fecha_solicitud', 'telefono')

# --- GESTIÓN DE USUARIOS DEL SISTEMA ---
admin.site.unregister(User)
admin.site.unregister(Group)

@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: 
            return qs
        # El dueño NO gestiona usuarios técnicos por aquí, 
        # gestiona "Empleados" en su propia sección.
        return qs.none()

admin.site.register(Group)
