from django.contrib import admin, messages
from django.contrib.auth.models import Group, User 
from django.urls import path, reverse 
from django.http import HttpResponseRedirect 
from django.utils.safestring import mark_safe 
import requests 
from .models import (
    Peluqueria, Servicio, Empleado, HorarioSemanal, Cita, PerfilUsuario, Ausencia
)

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
            del form.base_fields['peluqueria'] 
        return form

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
                obj.peluqueria = request.user.perfil.peluqueria
        super().save_model(request, obj, form, change)

class SuperuserOnlyAdmin(admin.ModelAdmin):
    def has_module_permission(self, request): return request.user.is_superuser
    
@admin.register(Peluqueria)
class PeluqueriaAdmin(SuperuserOnlyAdmin):
    # AHORA MOSTRAMOS LA CIUDAD EN EL ADMIN
    list_display = ('nombre', 'ciudad', 'slug', 'bold_status')
    list_filter = ('ciudad',) # FILTRO LATERAL POR CIUDAD
    prepopulated_fields = {'slug': ('nombre',)}
    
    @admin.display(description='Bold')
    def bold_status(self, obj):
        return "✅ Activa" if obj.bold_api_key else "❌ Inactiva"

    readonly_fields = ('boton_prueba_telegram',) 
    @admin.display(description='Telegram') 
    def boton_prueba_telegram(self, obj):
        if obj.pk: 
            url = reverse('admin:salon_peluqueria_test_telegram', args=[obj.pk])
            return mark_safe(f'<a class="button" href="{url}" style="background-color: #007bff; color: white; padding: 5px;">🔔 Probar</a>')
        return "-"
    
    def get_urls(self):
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name
        return [path('<path:object_id>/test_telegram/', self.admin_site.admin_view(self.test_telegram_view), name='%s_%s_test_telegram' % info)] + urls

    def test_telegram_view(self, request, object_id):
        try:
            peluqueria = self.get_object(request, str(object_id).split('/')[0])
            if not peluqueria: return HttpResponseRedirect("../")
            url_retorno = reverse('admin:salon_peluqueria_change', args=[peluqueria.pk])
            
            token = peluqueria.telegram_token
            chat_id = peluqueria.telegram_chat_id
            if not token or not chat_id:
                self.message_user(request, "⚠️ Faltan datos.", level=messages.WARNING)
                return HttpResponseRedirect(url_retorno)
            
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, data={"chat_id": chat_id, "text": "✅ Prueba Exitosa"}, timeout=3)
            self.message_user(request, "✅ Mensaje enviado.", level=messages.SUCCESS)
            return HttpResponseRedirect(url_retorno)
        except: return HttpResponseRedirect("../")

@admin.register(Servicio)
class ServicioAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'precio', 'str_duracion')
    exclude = ('peluqueria',)

@admin.register(Empleado)
class EmpleadoAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'apellido')
    exclude = ('peluqueria',)

@admin.register(Cita)
class CitaAdmin(SalonOwnerAdmin):
    list_display = ('cliente_nombre', 'empleado', 'fecha_hora_inicio', 'servicios_listados', 'estado') 
    filter_horizontal = ('servicios',) 
    exclude = ('peluqueria',) 
    
    def servicios_listados(self, obj):
        return ", ".join([s.nombre for s in obj.servicios.all()])

@admin.register(Ausencia)
class AusenciaAdmin(SalonOwnerAdmin): 
    list_display = ('empleado', 'fecha_inicio', 'fecha_fin')

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(SuperuserOnlyAdmin):
    list_display = ('user', 'peluqueria')

admin.site.unregister(User)
admin.site.unregister(Group)
admin.site.register(User)
admin.site.register(Group)
