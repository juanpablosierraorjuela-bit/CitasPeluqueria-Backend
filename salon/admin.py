from django.contrib import admin, messages
from django.contrib.auth.models import Group, User 
from django.urls import path, reverse 
from django.http import HttpResponseRedirect 
from django.utils.safestring import mark_safe 
import requests 
from .models import (
    Peluqueria, Servicio, Empleado, HorarioSemanal, Cita, PerfilUsuario
)

# CLASES BASE DE SEGURIDAD
class SalonOwnerAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
            return qs.filter(peluqueria=request.user.perfil.peluqueria)
        return qs.none()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser:
            if 'peluqueria' in form.base_fields: del form.base_fields['peluqueria'] 
        return form

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
                obj.peluqueria = request.user.perfil.peluqueria
        super().save_model(request, obj, form, change)

class SuperuserOnlyAdmin(admin.ModelAdmin):
    def has_module_permission(self, request): return request.user.is_superuser
    def has_view_permission(self, request, obj=None): return request.user.is_superuser
    def has_add_permission(self, request): return request.user.is_superuser
    def has_change_permission(self, request, obj=None): return request.user.is_superuser
    def has_delete_permission(self, request, obj=None): return request.user.is_superuser

# PELUQUERIA ADMIN (TELEGRAM AUTONOMO)
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
            token = str(peluqueria.telegram_token).strip() if peluqueria.telegram_token else None
            chat_id = str(peluqueria.telegram_chat_id).strip() if peluqueria.telegram_chat_id else None

            if not token or not chat_id:
                self.message_user(request, "⚠️ Faltan Token o ID.", level=messages.WARNING)
                return HttpResponseRedirect(url_retorno)
            
            url_api = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {"chat_id": chat_id, "text": "✅ *CONEXIÓN EXITOSA*\nBot activo.", "parse_mode": "Markdown"}
            
            resp = requests.post(url_api, data=data, timeout=5)
            if resp.status_code == 200 and resp.json().get('ok'):
                self.message_user(request, f"✅ Mensaje enviado a {peluqueria.nombre_visible}.", level=messages.SUCCESS)
            else:
                self.message_user(request, f"❌ Error Telegram: {resp.json()}", level=messages.ERROR)
            return HttpResponseRedirect(url_retorno)
        except Exception as e:
            self.message_user(request, f"❌ Error interno: {str(e)}", level=messages.ERROR)
            return HttpResponseRedirect("../")

# OTROS ADMINS
class HorarioSemanalInline(admin.TabularInline):
    model = HorarioSemanal
    extra = 1
    max_num = 7
    exclude = ('peluqueria',) 

@admin.register(Servicio)
class ServicioAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'precio', 'duracion')
    exclude = ('peluqueria',)

@admin.register(Empleado)
class EmpleadoAdmin(SalonOwnerAdmin):
    list_display = ('nombre', 'apellido')
    inlines = [HorarioSemanalInline]
    exclude = ('peluqueria',)

@admin.register(Cita)
class CitaAdmin(SalonOwnerAdmin):
    list_display = ('cliente_nombre', 'empleado', 'fecha_hora_inicio', 'servicios_listados', 'estado') 
    filter_horizontal = ('servicios',) 
    exclude = ('peluqueria',) 
    
    def servicios_listados(self, obj):
        return ", ".join([s.nombre for s in obj.servicios.all()])
    servicios_listados.short_description = 'Servicios'

try: admin.site.unregister(HorarioSemanal)
except: pass

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(SuperuserOnlyAdmin):
    list_display = ('user', 'peluqueria')

admin.site.unregister(User)
admin.site.unregister(Group)
class GlobalAdminUser(admin.ModelAdmin):
    def has_module_permission(self, request): return request.user.is_superuser
admin.site.register(User, GlobalAdminUser)
admin.site.register(Group, GlobalAdminUser)