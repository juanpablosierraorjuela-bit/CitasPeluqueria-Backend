from django.contrib import admin, messages
from django.contrib.auth.models import Group, User 
from django.urls import path, reverse 
from django.http import HttpResponseRedirect 
from django.utils.safestring import mark_safe 
import requests 
from .models import (
    Peluqueria, Servicio, Empleado, Cita, PerfilUsuario, Ausencia, SolicitudSaaS
)

# --- 1. ADMIN PARA DUEÑOS DE SALÓN ---
class SalonOwnerAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        # PROTECCIÓN: Solo filtramos si REALMENTE existe la peluquería
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

# --- 2. CONFIGURACIÓN DE PELUQUERÍA ---
@admin.register(Peluqueria)
class PeluqueriaAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
            return qs.filter(id=request.user.perfil.peluqueria.id)
        return qs.none()

    readonly_fields = ('boton_prueba_telegram', 'guia_telegram', 'guia_bold') 

    fieldsets = (
        ('🏢 Información del Negocio', {
            'fields': ('nombre', 'nombre_visible', 'ciudad', 'direccion', 'telefono')
        }),
        ('💳 Pagos con Bold (Configuración)', {
            'fields': ('guia_bold', 'porcentaje_abono', 'bold_api_key', 'bold_integrity_key'),
            'description': 'Configure aquí sus llaves de Bold.'
        }),
        ('🔔 Notificaciones Telegram (Configuración)', {
            'fields': ('guia_telegram', 'telegram_token', 'telegram_chat_id', 'boton_prueba_telegram'),
            'description': 'Conecte su celular para recibir avisos.'
        }),
    )

    @admin.display(description='📖 Ayuda Bold')
    def guia_bold(self, obj):
        url_webhook = "https://citaspeluqueria-backend.onrender.com/retorno-bold/"
        return mark_safe(f"""<div style="background-color: #fdf2f8; padding: 10px; border-left: 4px solid #ec4899;">URL Webhook: <b>{url_webhook}</b></div>""")

    @admin.display(description='📖 Ayuda Telegram')
    def guia_telegram(self, obj):
        return mark_safe("""<div style="background-color: #eff6ff; padding: 10px; border-left: 4px solid #3b82f6;">Usa @BotFather y @userinfobot.</div>""")

    @admin.display(description='Probar Conexión') 
    def boton_prueba_telegram(self, obj):
        if obj.pk: 
            url = reverse('admin:salon_peluqueria_test_telegram', args=[obj.pk])
            return mark_safe(f'<a class="button" href="{url}" style="background-color: #10b981; color: white;">🔔 Probar Telegram</a>')
        return "-"
    
    def get_urls(self):
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name
        return [path('<path:object_id>/test_telegram/', self.admin_site.admin_view(self.test_telegram_view), name='%s_%s_test_telegram' % info)] + urls

    def test_telegram_view(self, request, object_id):
        try:
            peluqueria = self.get_object(request, str(object_id).split('/')[0])
            if peluqueria and peluqueria.telegram_token and peluqueria.telegram_chat_id:
                requests.post(f"https://api.telegram.org/bot{peluqueria.telegram_token}/sendMessage", data={"chat_id": peluqueria.telegram_chat_id, "text": "✅ Test exitoso."}, timeout=3)
                self.message_user(request, "✅ Mensaje enviado.", level=messages.SUCCESS)
            else:
                self.message_user(request, "⚠️ Faltan datos.", level=messages.WARNING)
        except: pass
        return HttpResponseRedirect("../")

# --- 3. NUEVO: ADMIN TORRE DE CONTROL (TÚ) ---
@admin.register(SolicitudSaaS)
class SolicitudSaaSAdmin(admin.ModelAdmin):
    list_display = ('nombre_empresa', 'nicho', 'telefono', 'fecha_solicitud', 'atendido')
    list_filter = ('nicho', 'atendido')
    list_editable = ('atendido',)

# --- OTROS ADMINS ---
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
    list_display = ('cliente_nombre', 'empleado', 'fecha_hora_inicio', 'estado', 'precio_total') 
    filter_horizontal = ('servicios',) 
    exclude = ('peluqueria',) 

@admin.register(Ausencia)
class AusenciaAdmin(SalonOwnerAdmin): 
    list_display = ('empleado', 'fecha_inicio', 'fecha_fin')

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('user', 'peluqueria')

admin.site.unregister(User)
admin.site.unregister(Group)
admin.site.register(User)
admin.site.register(Group)
