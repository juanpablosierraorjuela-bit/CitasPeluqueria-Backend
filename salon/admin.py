from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms
from .models import (
    Peluqueria, Servicio, Empleado, Cita, PerfilUsuario, 
    Ausencia, SolicitudSaaS, HorarioEmpleado, ConfiguracionPlataforma,
    Producto, MovimientoInventario
)

# --- INLINE PARA INVENTARIO ---
class MovimientoInventarioInline(admin.TabularInline):
    model = MovimientoInventario
    extra = 0
    readonly_fields = ('fecha', 'tipo', 'cantidad', 'descripcion')
    can_delete = False

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cantidad_actual', 'precio_venta', 'es_insumo_interno', 'peluqueria')
    list_filter = ('es_insumo_interno', 'peluqueria')
    search_fields = ('nombre',)
    inlines = [MovimientoInventarioInline]
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
            return qs.filter(peluqueria=request.user.perfil.peluqueria)
        return qs.none()
    
    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.peluqueria = request.user.perfil.peluqueria
        super().save_model(request, obj, form, change)

# --- CONFIGURACIÓN GLOBAL ---
@admin.register(ConfiguracionPlataforma)
class ConfigAdmin(admin.ModelAdmin):
    list_display = ('link_pago_bold', 'precio_mensualidad')
    def has_add_permission(self, request):
        return self.model.objects.count() == 0

# --- CLASE BASE DE DUEÑOS ---
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
    list_display = ('nombre', 'apellido', 'peluqueria', 'es_domiciliario', 'es_independiente', 'activo')
    list_filter = ('es_domiciliario', 'es_independiente', 'activo', 'peluqueria')
    inlines = [HorarioEmpleadoInline]
    
    # Organización visual de campos para evitar errores al editar
    fieldsets = (
        ('Información Personal', {
            'fields': ('peluqueria', 'user', 'nombre', 'apellido', 'email_contacto', 'telefono', 'instagram', 'activo')
        }),
        ('Configuración Profesional', {
            'fields': ('es_domiciliario', 'tipo_pago', 'valor_pago')
        }),
        ('Modo Independiente (Credenciales Propias)', {
            'classes': ('collapse',),
            'description': 'Llenar SOLO si el empleado maneja sus propios cobros y notificaciones.',
            'fields': ('es_independiente', 'bold_api_key', 'bold_secret_key', 'telegram_token', 'telegram_chat_id')
        }),
    )

@admin.register(Servicio)
class ServicioAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'precio', 'duracion', 'producto_asociado') 
    exclude = ('peluqueria',)

@admin.register(Ausencia)
class AusenciaAdmin(SalonOwnerAdmin):
    list_display = ('empleado', 'fecha_inicio', 'fecha_fin')
    exclude = ('peluqueria',)

@admin.register(Cita)
class CitaAdmin(SalonOwnerAdmin):
    list_display = ('id', 'fecha_hora_inicio', 'cliente_nombre', 'empleado', 'precio_total', 'estado', 'metodo_pago')
    list_filter = ('estado', 'metodo_pago', 'fecha_hora_inicio')
    search_fields = ('cliente_nombre', 'referencia_pago')
    readonly_fields = ('creado_en',)
    exclude = ('peluqueria',)

@admin.register(Peluqueria)
class PeluqueriaAdmin(admin.ModelAdmin):
    list_display = ('nombre_visible', 'ciudad', 'telefono', 'fecha_inicio_contrato', 'activo_saas')
    search_fields = ('nombre', 'ciudad')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
            return qs.filter(id=request.user.perfil.peluqueria.id)
        return qs.none()

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('user', 'peluqueria', 'es_dueño')

@admin.register(SolicitudSaaS)
class SolicitudSaaSAdmin(admin.ModelAdmin):
    list_display = ('nombre_empresa', 'fecha_solicitud', 'telefono')

# Re-registrar User Admin
try: admin.site.unregister(User)
except admin.sites.NotRegistered: pass
try: admin.site.unregister(Group)
except admin.sites.NotRegistered: pass

@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    def get_queryset(self, request):
        if request.user.is_superuser: return super().get_queryset(request)
        return super().get_queryset(request).none()

admin.site.register(Group)
