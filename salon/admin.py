from django.contrib import admin, messages
from django.contrib.auth.models import Group, User 
from django.urls import path, reverse # <--- AGREGADO: reverse para obtener URLs reales
from django.http import HttpResponseRedirect # <--- AGREGADO: Para redireccionar correctamente
from django.utils.safestring import mark_safe 
from .models import (
    Peluqueria, Servicio, Empleado, HorarioSemanal, Cita, PerfilUsuario,
    enviar_mensaje_telegram 
)

# =============================================================
# 1. CLASES BASE DE SEGURIDAD Y VISIBILIDAD
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

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and not obj.pk:
            if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
                obj.peluqueria = request.user.perfil.peluqueria
        super().save_model(request, obj, form, change)
        
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


# 2. CLASE INLINE PARA HORARIOS
class HorarioSemanalInline(admin.TabularInline):
    """Permite editar los horarios directamente desde el formulario de Empleado."""
    model = HorarioSemanal
    extra = 7
    max_num = 7


# =============================================================
# 3. REGISTRO DE MODELOS (Con el Botón de Prueba en Peluqueria)
# =============================================================

@admin.register(Peluqueria)
class PeluqueriaAdmin(SuperuserOnlyAdmin):
    list_display = ('nombre', 'slug', 'nombre_visible', 'boton_prueba_telegram')
    prepopulated_fields = {'slug': ('nombre',)}
    
    # Campo de solo lectura para mostrar el botón
    readonly_fields = ('boton_prueba_telegram',) 
    
    # --- MÉTODO PARA CREAR EL BOTÓN VISUALMENTE ---
    @admin.display(description='Diagnóstico Telegram') 
    def boton_prueba_telegram(self, obj):
        if obj.pk: 
            # FIX: Usamos una ruta relativa segura para llegar a la vista personalizada
            url = f"../{obj.pk}/test_telegram/" 
            return mark_safe(f'<a class="button" href="{url}" style="background-color: #007bff; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;">Enviar Mensaje de Prueba</a>')
        return "Guarde la peluquería para probar"
    
    # --- FUNCIÓN QUE AÑADE LA RUTA AL BOTÓN ---
    def get_urls(self):
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name
        
        extra_urls = [
            path('<path:object_id>/test_telegram/', self.admin_site.admin_view(self.test_telegram_view), name='%s_%s_test_telegram' % info),
        ]
        return extra_urls + urls

    # --- FUNCIÓN QUE EJECUTA LA LÓGICA DE TELEGRAM ---
    def test_telegram_view(self, request, object_id):
        peluqueria = self.get_object(request, object_id)
        
        # URL de retorno: Calculamos la URL exacta de "editar peluquería"
        url_retorno = reverse('admin:salon_peluqueria_change', args=[peluqueria.pk])

        if not peluqueria.telegram_token or not peluqueria.telegram_chat_id:
            self.message_user(request, "Error: Por favor, configure el Token y el ID de Chat antes de probar.", level=messages.ERROR)
            # FIX: Redirección explicita en lugar de self.change_view
            return HttpResponseRedirect(url_retorno)
        
        mensaje_prueba = (
            f"✅ *PRUEBA EXITOSA!*\n\n"
            f"El Bot de Telegram está funcionando para el salón: *{peluqueria.nombre_visible}*."
        )

        exito, resultado = enviar_mensaje_telegram(peluqueria.telegram_token, peluqueria.telegram_chat_id, mensaje_prueba)
        
        if exito:
            self.message_user(request, f"Mensaje de prueba enviado con éxito a {peluqueria.nombre}.", level=messages.SUCCESS)
        else:
            self.message_user(request, f"Fallo al enviar el mensaje: {resultado}. Verifique el Chat ID (con el signo -) y el Token.", level=messages.ERROR)
        
        # FIX FINAL: Redireccionamos al usuario a la página de edición para evitar errores 404/Pantalla blanca
        return HttpResponseRedirect(url_retorno)


# Modelos Transaccionales (Visibles para Dueños)

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

# Desregistramos HorarioSemanal
try:
    admin.site.unregister(HorarioSemanal)
except admin.sites.NotRegistered:
    pass

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(SuperuserOnlyAdmin):
    list_display = ('user', 'peluqueria')
    pass 


# 4. OCULTAR "AUTENTICACIÓN Y AUTORIZACIÓN"
admin.site.unregister(User)
admin.site.unregister(Group)

class GlobalAdminUser(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_superuser

admin.site.register(User, GlobalAdminUser)
admin.site.register(Group, GlobalAdminUser)