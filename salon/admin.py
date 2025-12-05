import requests  # NECESARIO PARA PROBAR TELEGRAM
from django.contrib import admin, messages
from .models import Peluqueria, Servicio, Empleado, Cita, PerfilUsuario, HorarioSemanal

# --- CONFIGURACIÓN DE TABLA INTERNA (INLINE) ---
class HorarioInline(admin.TabularInline):
    model = HorarioSemanal
    extra = 0
    can_delete = True
    fields = ('dia_semana', 'hora_inicio', 'hora_fin', 'descanso_inicio', 'descanso_fin')
    ordering = ('dia_semana',)

# --- ADMIN DE PELUQUERÍA (EL MÁS IMPORTANTE) ---
@admin.register(Peluqueria)
class PeluqueriaAdmin(admin.ModelAdmin):
    # Columnas que ves en la lista principal
    list_display = ('nombre_visible', 'telefono', 'direccion', 'bot_activo', 'hora_apertura', 'hora_cierre')
    
    # Barra de búsqueda
    search_fields = ('nombre', 'nombre_visible', 'telefono')
    
    # Slug automático
    prepopulated_fields = {'slug': ('nombre',)}

    # Acciones personalizadas (Menú desplegable "Action")
    actions = ['enviar_prueba_telegram']

    # ORGANIZACIÓN POR SECCIONES
    fieldsets = (
        ('Datos del Negocio', {
            'fields': ('nombre', 'nombre_visible', 'slug')
        }),
        ('Contacto', {
            'fields': ('direccion', 'telefono')
        }),
        ('Horarios Generales', {
            'fields': ('hora_apertura', 'hora_cierre')
        }),
        ('Configuración de Notificaciones (Telegram)', {
            'fields': ('telegram_token', 'telegram_chat_id'),
            'description': 'Ingresa aquí el Token del BotFather y tu ID de usuario para recibir avisos.',
            'classes': ('collapse',), 
        }),
    )

    # Función para mostrar un ✅ si el bot está configurado
    @admin.display(boolean=True, description='Bot Configurado')
    def bot_activo(self, obj):
        token = str(obj.telegram_token).strip() if obj.telegram_token else ''
        chat_id = str(obj.telegram_chat_id).strip() if obj.telegram_chat_id else ''
        return bool(token and chat_id)

    # --- NUEVA FUNCIÓN DE DIAGNÓSTICO AVANZADA ---
    @admin.action(description='🔔 Enviar mensaje de prueba a Telegram')
    def enviar_prueba_telegram(self, request, queryset):
        enviados = 0
        errores = 0
        
        for peluqueria in queryset:
            # 1. LIMPIEZA DE DATOS (Vital por si copiaste con espacios)
            token = str(peluqueria.telegram_token).strip() if peluqueria.telegram_token else ""
            chat_id = str(peluqueria.telegram_chat_id).strip() if peluqueria.telegram_chat_id else ""
            
            # Identificador visual del token (para que sepas cuál está usando)
            token_visible = f"...{token[-4:]}" if len(token) > 4 else "N/A"

            if not token or not chat_id:
                self.message_user(request, f"⚠️ {peluqueria.nombre_visible}: Falta Token o ID en la base de datos.", level=messages.WARNING)
                errores += 1
                continue

            # 2. INTENTO DE ENVÍO
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            mensaje_prueba = (
                f"✅ *¡CONEXIÓN ESTABLECIDA!*\n"
                f"Hola {peluqueria.nombre_visible}.\n"
                f"Este bot está configurado correctamente con el token terminado en *{token_visible}*."
            )
            
            data = {
                "chat_id": chat_id, 
                "text": mensaje_prueba, 
                "parse_mode": "Markdown"
            }
            
            try:
                # Timeout corto para no colgar el admin si falla
                response = requests.post(url, data=data, timeout=5)
                res_json = response.json()
                
                if response.status_code == 200 and res_json.get('ok'):
                    enviados += 1
                else:
                    errores += 1
                    # ERROR DETALLADO QUE DEVUELVE TELEGRAM
                    desc = res_json.get('description', 'Error desconocido')
                    error_msg = f"❌ Error en {peluqueria.nombre_visible} (Token finaliza en {token_visible}): {desc}"
                    
                    # Pistas comunes para ayudarte
                    if "Unauthorized" in desc:
                        error_msg += " -> EL TOKEN ESTÁ MAL O REVOCADO."
                    elif "chat not found" in desc:
                        error_msg += " -> EL CHAT ID ESTÁ MAL O NO HAS INICIADO EL BOT."
                        
                    self.message_user(request, error_msg, level=messages.ERROR)
                    
            except Exception as e:
                errores += 1
                self.message_user(request, f"❌ Error de conexión: {str(e)}", level=messages.ERROR)

        if enviados > 0:
            self.message_user(request, f"✅ Se enviaron {enviados} mensajes correctamente.", level=messages.SUCCESS)

# --- OTROS ADMINS ---

@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'peluqueria', 'precio', 'duracion')
    list_filter = ('peluqueria',) # Filtro lateral para ver servicios por peluquería
    search_fields = ('nombre',)

@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'apellido', 'peluqueria')
    list_filter = ('peluqueria',)
    inlines = [HorarioInline]

@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    # Agregamos 'servicios_lista' para ver qué pidieron
    list_display = ('cliente_nombre', 'peluqueria', 'empleado', 'fecha_hora_inicio', 'servicios_lista', 'precio_total', 'estado')
    list_filter = ('estado', 'peluqueria', 'fecha_hora_inicio')
    search_fields = ('cliente_nombre', 'cliente_telefono')
    date_hierarchy = 'fecha_hora_inicio' # Navegación por fecha arriba de la tabla
    
    # Permite editar el estado directamente desde la lista sin entrar
    list_editable = ('estado',) 

    def servicios_lista(self, obj):
        return ", ".join([s.nombre for s in obj.servicios.all()])
    servicios_lista.short_description = "Servicios Solicitados"

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('user', 'peluqueria')