from django.contrib import admin, messages
from django.contrib.auth.models import Group, User 
from django.urls import path, reverse 
from django.http import HttpResponseRedirect 
from django.utils.safestring import mark_safe 
import requests 
from .models import (
    Peluqueria, Servicio, Empleado, HorarioSemanal, Cita, PerfilUsuario, Ausencia
)

# --- 1. ADMIN PARA DUEÑOS DE SALÓN ---
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

# --- 2. CONFIGURACIÓN DE PELUQUERÍA (Aquí está la magia SaaS) ---
@admin.register(Peluqueria)
class PeluqueriaAdmin(admin.ModelAdmin):
    # Esto asegura que el dueño solo vea SU peluquería
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
            return qs.filter(id=request.user.perfil.peluqueria.id)
        return qs.none()

    # Campos organizados por secciones
    fieldsets = (
        ('Información del Negocio', {
            'fields': ('nombre', 'nombre_visible', 'ciudad', 'direccion', 'telefono')
        }),
        ('💳 Configuración de Pagos (Bold)', {
            'fields': ('porcentaje_abono', 'bold_api_key', 'bold_integrity_key'),
            'description': 'Configure aquí sus llaves de Bold para recibir dinero directamente.'
        }),
        ('🔔 Notificaciones (Telegram)', {
            'fields': ('telegram_token', 'telegram_chat_id', 'boton_prueba_telegram'),
            'description': 'Configure aquí su Bot para recibir alertas de nuevas citas.'
        }),
    )

    readonly_fields = ('boton_prueba_telegram',) 
    
    @admin.display(description='Telegram') 
    def boton_prueba_telegram(self, obj):
        if obj.pk: 
            url = reverse('admin:salon_peluqueria_test_telegram', args=[obj.pk])
            return mark_safe(f'<a class="button" href="{url}" style="background-color: #007bff; color: white; padding: 5px; border-radius: 5px;">🔔 Enviar Mensaje de Prueba</a>')
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
                self.message_user(request, "⚠️ Faltan datos de Telegram.", level=messages.WARNING)
                return HttpResponseRedirect(url_retorno)
            
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, data={"chat_id": chat_id, "text": "✅ ¡Conexión Exitosa con PASO!"}, timeout=3)
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
    list_display = ('cliente_nombre', 'empleado', 'fecha_hora_inicio', 'estado', 'precio_total', 'abono_pagado') 
    filter_horizontal = ('servicios',) 
    exclude = ('peluqueria',) 

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
