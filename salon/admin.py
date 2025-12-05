from django.contrib import admin
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

    # ORGANIZACIÓN POR SECCIONES (Aquí agregué los campos que faltaban)
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
            'classes': ('collapse',), # Esto permite ocultar/mostrar esta sección
        }),
    )

    # Función para mostrar un ✅ si el bot está configurado
    @admin.display(boolean=True, description='Bot Configurado')
    def bot_activo(self, obj):
        return bool(obj.telegram_token and obj.telegram_chat_id)

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