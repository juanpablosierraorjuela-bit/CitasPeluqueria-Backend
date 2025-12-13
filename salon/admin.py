from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms
from .models import Peluqueria, Servicio, Empleado, Cita, PerfilUsuario, Ausencia, SolicitudSaaS, HorarioEmpleado, ConfiguracionPlataforma, Producto, MovimientoInventario

class MovimientoInventarioInline(admin.TabularInline):
    model = MovimientoInventario
    extra = 0
    readonly_fields = ('fecha', 'tipo', 'cantidad', 'descripcion')
    can_delete = False
    def has_add_permission(self, request, obj): return False

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cantidad_actual', 'precio_venta', 'peluqueria')
    inlines = [MovimientoInventarioInline]
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
            return qs.filter(peluqueria=request.user.perfil.peluqueria)
        return qs.none()
    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser: obj.peluqueria = request.user.perfil.peluqueria
        super().save_model(request, obj, form, change)

@admin.register(ConfiguracionPlataforma)
class ConfigAdmin(admin.ModelAdmin):
    list_display = ('link_pago_bold', 'precio_mensualidad')
    def has_add_permission(self, request): return self.model.objects.count() == 0

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
        if not request.user.is_superuser: obj.peluqueria = request.user.perfil.peluqueria
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
    list_filter = ('es_domiciliario', 'es_independiente', 'activo')
    inlines = [HorarioEmpleadoInline]
    fieldsets = (
        ('Info', {'fields': ('peluqueria', 'user', 'nombre', 'apellido', 'email_contacto', 'telefono', 'instagram', 'activo')}),
        ('Config', {'fields': ('es_domiciliario', 'tipo_pago', 'valor_pago')}),
        ('Independiente', {'classes': ('collapse',), 'fields': ('es_independiente', 'bold_api_key', 'bold_secret_key', 'telegram_token', 'telegram_chat_id')}),
    )

@admin.register(Servicio)
class ServicioAdmin(SalonOwnerAdmin): list_display = ('nombre', 'precio', 'duracion'); exclude = ('peluqueria',)
@admin.register(Ausencia)
class AusenciaAdmin(SalonOwnerAdmin): list_display = ('empleado', 'fecha_inicio'); exclude = ('peluqueria',)
@admin.register(Cita)
class CitaAdmin(SalonOwnerAdmin):
    list_display = ('id', 'fecha_hora_inicio', 'cliente_nombre', 'empleado', 'estado', 'metodo_pago')
    list_filter = ('estado', 'metodo_pago'); exclude = ('peluqueria',)

@admin.register(Peluqueria)
class PeluqueriaAdmin(admin.ModelAdmin):
    list_display = ('nombre_visible', 'ciudad', 'telefono'); search_fields = ('nombre',)
    def get_queryset(self, request):
        if request.user.is_superuser: return super().get_queryset(request)
        if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria: return super().get_queryset(request).filter(id=request.user.perfil.peluqueria.id)
        return super().get_queryset(request).none()

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin): list_display = ('user', 'peluqueria', 'es_dueño')
@admin.register(SolicitudSaaS)
class SolicitudSaaSAdmin(admin.ModelAdmin): list_display = ('nombre_empresa', 'fecha_solicitud')

try: admin.site.unregister(User); admin.site.unregister(Group)
except: pass
@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    def get_queryset(self, request): return super().get_queryset(request) if request.user.is_superuser else super().get_queryset(request).none()
admin.site.register(Group)
