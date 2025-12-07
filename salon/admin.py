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

# --- 2. CONFIGURACIÓN DE PELUQUERÍA (MODO TUTORIAL) ---
@admin.register(Peluqueria)
class PeluqueriaAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
            return qs.filter(id=request.user.perfil.peluqueria.id)
        return qs.none()

    # --- CAMPOS DE SOLO LECTURA (LAS GUÍAS) ---
    readonly_fields = ('boton_prueba_telegram', 'guia_telegram', 'guia_bold') 

    # --- ORDEN VISUAL DEL FORMULARIO ---
    fieldsets = (
        ('🏢 Información del Negocio', {
            'fields': ('nombre', 'nombre_visible', 'ciudad', 'direccion', 'telefono')
        }),
        ('💳 Pagos con Bold (Configuración)', {
            'fields': ('guia_bold', 'porcentaje_abono', 'bold_api_key', 'bold_integrity_key'),
            'description': 'Configure aquí sus llaves de Bold para recibir el dinero en su cuenta bancaria.'
        }),
        ('🔔 Notificaciones Telegram (Configuración)', {
            'fields': ('guia_telegram', 'telegram_token', 'telegram_chat_id', 'boton_prueba_telegram'),
            'description': 'Conecte su celular para recibir avisos inmediatos.'
        }),
    )

    # --- GUÍA VISUAL PARA BOLD ---
    @admin.display(description='📖 ¿Cómo configurar Bold?')
    def guia_bold(self, obj):
        # NOTA: Cambia esta URL si tienes un dominio propio (ej: https://citas.pasotunja.com/retorno-bold/)
        url_webhook = "https://citaspeluqueria-backend.onrender.com/retorno-bold/"
        
        return mark_safe(f"""
            <div style="background-color: #fdf2f8; border-left: 5px solid #ec4899; padding: 15px; border-radius: 4px; color: #333;">
                <h4 style="margin-top:0; color: #be185d;">🚀 Pasos para activar pagos:</h4>
                <ol style="margin-left: 20px; line-height: 1.6;">
                    <li>Inicia sesión en tu cuenta de <b>Bold.co</b> (Panel de Comercios).</li>
                    <li>Ve al menú <b>Integraciones</b> o <b>Desarrolladores</b>.</li>
                    <li>Copia la <b>"Llave de Identidad"</b> y pégala abajo en el campo <em>Bold Integrity Key</em>.</li>
                    <li>Copia la <b>"Llave Pública" (PK)"</b> y pégala abajo en el campo <em>Bold Api Key</em>.</li>
                    <li>Si Bold te pide una <b>"URL de Retorno"</b> o Webhook, copia y pega exactamente este enlace:</li>
                </ol>
                <div style="background: white; padding: 10px; border: 1px dashed #ec4899; font-family: monospace; font-weight: bold; text-align: center;">
                    {url_webhook}
                </div>
            </div>
        """)

    # --- GUÍA VISUAL PARA TELEGRAM ---
    @admin.display(description='📖 ¿Cómo crear el Bot?')
    def guia_telegram(self, obj):
        return mark_safe("""
            <div style="background-color: #eff6ff; border-left: 5px solid #3b82f6; padding: 15px; border-radius: 4px; color: #333;">
                <h4 style="margin-top:0; color: #1d4ed8;">🤖 Pasos para activar notificaciones:</h4>
                <ol style="margin-left: 20px; line-height: 1.6;">
                    <li>Abre la app de Telegram y busca el usuario <b>@BotFather</b>.</li>
                    <li>Escribe el comando <code>/newbot</code> y sigue las instrucciones para ponerle nombre.</li>
                    <li>Al final te dará un <b>TOKEN</b> (letras y números raros). Cópialo y pégalo abajo en <em>Telegram Token</em>.</li>
                    <li>Ahora, busca el usuario <b>@userinfobot</b> en Telegram y dale "Iniciar".</li>
                    <li>Te responderá con tu <b>Id</b> (un número). Cópialo y pégalo abajo en <em>Telegram Chat ID</em>.</li>
                    <li><b>¡IMPORTANTE!</b> Busca tu nuevo bot en Telegram y dale "Iniciar" para que pueda escribirte.</li>
                </ol>
            </div>
        """)

    # --- BOTÓN DE PRUEBA ---
    @admin.display(description='Probar Conexión') 
    def boton_prueba_telegram(self, obj):
        if obj.pk: 
            url = reverse('admin:salon_peluqueria_test_telegram', args=[obj.pk])
            return mark_safe(f'<a class="button" href="{url}" style="background-color: #10b981; color: white; padding: 8px 15px; border-radius: 20px; font-weight:bold;">🔔 Enviar Mensaje de Prueba al Celular</a>')
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
                self.message_user(request, "⚠️ Faltan datos para probar.", level=messages.WARNING)
                return HttpResponseRedirect(url_retorno)
            
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, data={"chat_id": chat_id, "text": "✅ ¡Hola! Tu sistema de citas PASO está conectado correctamente."}, timeout=3)
            self.message_user(request, "✅ Mensaje de prueba enviado. Revisa tu Telegram.", level=messages.SUCCESS)
            return HttpResponseRedirect(url_retorno)
        except: return HttpResponseRedirect("../")

# --- OTROS ADMINS (No cambian) ---
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
# ... (todo tu código anterior) ...
from .models import SolicitudSaaS # <--- Asegúrate de importar esto arriba o aquí

@admin.register(SolicitudSaaS)
class SolicitudSaaSAdmin(admin.ModelAdmin):
    list_display = ('nombre_empresa', 'nicho', 'cantidad_empleados', 'telefono', 'fecha_solicitud', 'atendido')
    list_filter = ('nicho', 'cantidad_empleados', 'atendido')
    search_fields = ('nombre_empresa', 'nombre_contacto', 'telefono')
    list_editable = ('atendido',)
