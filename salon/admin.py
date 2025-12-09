from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms
from .models import Peluqueria, Servicio, Empleado, Cita, PerfilUsuario, Ausencia, SolicitudSaaS, HorarioEmpleado

# --- INLINE PARA HORARIOS (La magia del control de tiempo) ---
class HorarioInline(admin.TabularInline):
    model = HorarioEmpleado
    extra = 0
    min_num = 1
    verbose_name = "Jornada Laboral"
    verbose_name_plural = "Configurar Días y Horas de Trabajo"
    help_text = "Agrega aquí los días y horas que este empleado trabaja."

# --- ADMIN BASE PARA DUEÑOS ---
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
            # Ocultamos el campo peluquería, se asigna automática
            form.base_fields['peluqueria'].widget = forms.HiddenInput()
        return form

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
                obj.peluqueria = request.user.perfil.peluqueria
        super().save_model(request, obj, form, change)

# --- EMPLEADO ADMIN (CON HORARIOS) ---
@admin.register(Empleado)
class EmpleadoAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'apellido', 'activo')
    inlines = [HorarioInline] # <--- ¡Aquí aparecen los horarios!
    exclude = ('peluqueria',)

@admin.register(Servicio)
class ServicioAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'precio', 'str_duracion')
    exclude = ('peluqueria',)

@admin.register(Cita)
class CitaAdmin(SalonOwnerAdmin):
    list_display = ('cliente_nombre', 'empleado', 'fecha_hora_inicio', 'estado', 'precio_total')
    list_filter = ('estado', 'fecha_hora_inicio', 'empleado')
    exclude = ('peluqueria',)

# --- REGISTRO SAAS (Para ti) ---
@admin.register(SolicitudSaaS)
class SolicitudSaaSAdmin(admin.ModelAdmin):
    list_display = ('nombre_empresa', 'telefono', 'fecha_solicitud')

@admin.register(Peluqueria)
class PeluqueriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'ciudad', 'telefono')

# --- USER CUSTOM ADMIN (Permisos con chulitos) ---
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
admin.site.register(PerfilUsuario)
admin.site.register(Ausencia)
