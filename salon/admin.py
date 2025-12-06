from django.contrib import admin, messages
from django.contrib.auth.models import Group, User 
from django.urls import path, reverse 
from django.http import HttpResponseRedirect 
from django.utils.safestring import mark_safe 
from .models import (
    Peluqueria, Servicio, Empleado, HorarioSemanal, Cita, PerfilUsuario,
    enviar_mensaje_telegram 
)

# =============================================================
# 1. CLASES BASE DE SEGURIDAD
# =============================================================

class SalonOwnerAdmin(admin.ModelAdmin):
    """Clase base para modelos que el Dueño SÍ debe ver y gestionar."""
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
            return qs.filter(peluqueria=request.user.perfil.peluqueria)
        return qs.none()

    # 1. Al guardar el modelo PRINCIPAL (Ej: Empleado), le ponemos su peluquería
    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and not obj.pk:
            if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
                obj.peluqueria = request.user.perfil.peluqueria
        super().save_model(request, obj, form, change)

    # 2. Al guardar los INLINES (Ej: Horarios), les inyectamos la peluquería a la fuerza
    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            # Si el usuario es dueño y el objeto necesita peluqueria
            if not request.user.is_superuser:
                if hasattr(instance, 'peluqueria') and hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
                    instance.peluqueria = request.user.perfil.peluqueria
            instance.save()
        formset.save_m2m()
        
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser:
            if 'peluqueria' in form.base_fields:
                form.base_fields['peluqueria'].widget.attrs['disabled'] = True
                form.base_fields['peluqueria'].required = False
        return form

class SuperuserOnlyAdmin(admin.ModelAdmin):
    """Clase base que oculta el modelo completamente de la barra lateral."""
    def has_module_permission(self, request):
        return request.user.is_superuser
    def has_view_permission(self, request, obj=None): return request.user.is_superuser
    def has_add_permission(self, request): return request.user.is_superuser
    def has_change_permission(self, request, obj=None): return request.user.is_superuser
    def has_delete_permission(self, request, obj=None): return request.user.is_superuser


# =============================================================
# 2. PELUQUERIA ADMIN (Con Botón Telegram)
# =============================================================

@admin.register(Peluqueria)
class PeluqueriaAdmin(SuperuserOnlyAdmin):
    list_display = ('nombre', 'slug', 'nombre_visible', 'boton_prueba_telegram')
    prepopulated_fields = {'slug': ('nombre',)}
    readonly_fields = ('boton_prueba_telegram',) 
    
    @admin.display(description='Diagnóstico Telegram') 
    def boton_prueba_telegram(self, obj):
        if obj.pk: 
            url = f"../{obj.pk}/test_telegram/" 
            return mark_safe(f'<a class="button" href="{url}" style="background-color: #007bff; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;">Enviar Mensaje de Prueba</a>')
        return "Guarde la peluquería para probar"
    
    def get_urls(self):
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name
        extra_urls = [
            path('<path:object_id>/test_telegram/', self.admin_site.admin_view(self.test_telegram_view), name='%s_%s_test_telegram' % info),
        ]
        return extra_urls + urls

    def test_telegram_view(self, request, object_id):
        try:
            peluqueria = self.get_object(request, object_id)
            url_retorno = reverse('admin:salon_peluqueria_change', args=[peluqueria.pk])

            if not peluqueria.telegram_token or not peluqueria.telegram_chat_id:
                self.message_user(request, "Error: Faltan datos de Telegram.", level=messages.ERROR)
                return HttpResponseRedirect(url_retorno)
            
            exito, resultado = enviar_mensaje_telegram(
                peluqueria.telegram_token, 
                peluqueria.telegram_chat_id, 
                f"✅ *TEST EXITOSO*\nHola desde PASO Tunja. Tu sistema funciona."
            )
            
            if exito:
                self.message_user(request, f"¡Éxito! Mensaje enviado.", level=messages.SUCCESS)
            else:
                self.message_user(request, f"Error de Telegram: {resultado}", level=messages.ERROR)
            
            return HttpResponseRedirect(url_retorno)

        except Exception as e:
            self.message_user(request, f"Error interno del sistema: {str(e)}", level=messages.ERROR)
            return HttpResponseRedirect("../")


# =============================================================
# 3. CONFIGURACIÓN DE MODELOS E INLINES
# =============================================================

class HorarioSemanalInline(admin.TabularInline):
    """
    Inline para editar horarios dentro del Empleado.
    IMPORTANTE: Excluimos 'peluqueria' para que no pida el dato en el formulario,
    ya que lo rellenamos automáticamente en save_formset.
    """
    model = HorarioSemanal
    extra = 1
    max_num = 7
    exclude = ('peluqueria',)  # <--- ¡ESTA LÍNEA EVITA EL ERROR 500!

@admin.register(Servicio)
class ServicioAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'precio', 'duracion')

@admin.register(Empleado)
class EmpleadoAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'apellido')
    inlines = [HorarioSemanalInline] 

@admin.register(Cita)
class CitaAdmin(SalonOwnerAdmin):
    list_display = ('cliente_nombre', 'empleado', 'fecha_hora_inicio', 'servicios_listados', 'estado') 
    filter_horizontal = ('servicios',) 
    def servicios_listados(self, obj):
        return ", ".join([s.nombre for s in obj.servicios.all()])
    servicios_listados.short_description = 'Servicios'

# Desregistramos HorarioSemanal suelto para evitar confusiones
try:
    admin.site.unregister(HorarioSemanal)
except admin.sites.NotRegistered:
    pass

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(SuperuserOnlyAdmin):
    list_display = ('user', 'peluqueria')

admin.site.unregister(User)
admin.site.unregister(Group)

class GlobalAdminUser(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_superuser

admin.site.register(User, GlobalAdminUser)
admin.site.register(Group, GlobalAdminUser)