from django.contrib import admin, messages # Necesitamos 'messages'
from django.contrib.auth.models import Group, User 
from .models import Peluqueria, Servicio, Empleado, HorarioSemanal, Cita, PerfilUsuario, enviar_mensaje_telegram # Importamos la función

# ... (Las clases SalonOwnerAdmin, SuperuserOnlyAdmin, y las demás clases de modelos siguen aquí) ...

# 3. SEGURIDAD DE VISIBILIDAD DE ADMINISTRACIÓN (SOLO PARA SUPERUSUARIO)

@admin.register(Peluqueria)
class PeluqueriaAdmin(SuperuserOnlyAdmin):
    list_display = ('nombre', 'slug', 'nombre_visible', 'boton_prueba_telegram') # Añadimos el botón a la lista
    prepopulated_fields = {'slug': ('nombre',)}
    
    # Este campo se añadirá al formulario de edición de la Peluquería
    readonly_fields = ('boton_prueba_telegram',) 
    
    # --- MÉTODO PARA CREAR EL BOTÓN DE PRUEBA ---
    def boton_prueba_telegram(self, obj):
        if obj.pk: # Solo si el objeto ya existe
            # Creamos la URL para llamar a nuestro método
            url = f"test_telegram/{obj.pk}/"
            return f'<a class="button" href="{url}">Enviar Mensaje de Prueba</a>'
        return "Guarde la peluquería para probar"
    
    boton_prueba_telegram.short_description = 'Diagnóstico Telegram'
    boton_prueba_telegram.allow_tags = True
    
    # --- FUNCIÓN QUE MANEJA EL CLICK DEL BOTÓN ---
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name
        
        # Añadimos una URL personalizada que llama a la vista 'test_telegram_view'
        extra_urls = [
            path('<path:object_id>/test_telegram/', self.admin_site.admin_view(self.test_telegram_view), name='%s_%s_test_telegram' % info),
        ]
        return extra_urls + urls

    def test_telegram_view(self, request, object_id, extra_context=None):
        peluqueria = self.get_object(request, object_id)
        
        if not peluqueria.telegram_token or not peluqueria.telegram_chat_id:
            self.message_user(request, "Error: Por favor, configure el Token y el ID de Chat antes de probar.", level=messages.ERROR)
            return self.change_view(request, object_id)
        
        mensaje_prueba = (
            f"✅ *PRUEBA EXITOSA!*\n\n"
            f"El Bot de Telegram está funcionando para el salón: *{peluqueria.nombre_visible}*."
        )

        exito, resultado = enviar_mensaje_telegram(peluqueria.telegram_token, peluqueria.telegram_chat_id, mensaje_prueba)
        
        if exito:
            self.message_user(request, f"Mensaje de prueba enviado con éxito a {peluqueria.nombre}.", level=messages.SUCCESS)
        else:
            self.message_user(request, f"Fallo al enviar el mensaje: {resultado}. Verifique el Chat ID y el Token.", level=messages.ERROR)
        
        # Redirige de vuelta al formulario de edición
        return self.change_view(request, object_id)

    # ... (El resto del código de PeluqueriaAdmin y las demás clases siguen igual)