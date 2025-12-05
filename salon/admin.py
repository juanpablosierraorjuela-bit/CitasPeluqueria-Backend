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
        return bool(obj.telegram_token and obj.telegram_chat_id)

    # --- NUEVA FUNCIÓN DE DIAGNÓSTICO ---
    @admin.action(description='🔔 Enviar mensaje de prueba a Telegram')
    def enviar_prueba_telegram(self, request, queryset):
        enviados = 0
        errores = 0
        
        for peluqueria in queryset:
            token = peluqueria.telegram_token
            chat_id = peluqueria.telegram_chat_id
            
            if not token or not chat_id:
                self.message_user(request, f"⚠️ {peluqueria.nombre_visible}: Falta Token o ID.", level=messages.WARNING)
                errores += 1
                continue

            # Intentamos enviar el mensaje
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {
                "chat_id": chat_id, 
                "text": f"✅ *¡Conexión Exitosa!*\nHola {peluqueria.nombre_visible}, tu bot está funcionando perfectamente.", 
                "parse_mode": "Markdown"
            }
            
            try:
                response = requests.post(url, data=data, timeout=5)
                res_json = response.json()
                
                if response.status_code == 200 and res_json.get('ok'):
                    enviados += 1
                else:
                    errores += 1
                    desc = res_json.get('description', 'Error desconocido')
                    # Mostramos el error exacto que devuelve Telegram
                    self.message_user(request, f"❌ Error en {peluqueria.nombre_visible}: {desc}", level=messages.ERROR)
            except Exception as e:
                errores += 1
                self.message_user(request, f"❌ Error de conexión: {str(e)}", level=messages.ERROR)

        if enviados > 0:
            self.message_user(request, f"✅ Se enviaron {enviados} mensajes de prueba correctamente.", level=messages.SUCCESS)

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