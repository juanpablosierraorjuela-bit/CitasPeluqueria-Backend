from django.contrib import admin
from .models import Peluqueria, Servicio, Empleado, Cita, PerfilUsuario, HorarioSemanal

# --- CONFIGURACIÓN DE TABLA INTERNA (INLINE) ---
# Esto permite ver y editar los horarios DENTRO de la pantalla del empleado
class HorarioInline(admin.TabularInline):
    model = HorarioSemanal
    extra = 0  # No crea filas vacías extra
    can_delete = True
    fields = ('dia_semana', 'hora_inicio', 'hora_fin', 'descanso_inicio', 'descanso_fin')
    ordering = ('dia_semana',) # Ordena de Lunes (0) a Domingo (6)

# --- ADMIN PRINCIPAL ---

@admin.register(Peluqueria)
class PeluqueriaAdmin(admin.ModelAdmin):
    # Agregamos hora_apertura y hora_cierre para que puedas controlarlas
    list_display = ('nombre', 'nombre_visible', 'hora_apertura', 'hora_cierre', 'telegram_chat_id', 'slug')
    fields = ('nombre', 'nombre_visible', 'hora_apertura', 'hora_cierre', 'telegram_chat_id', 'slug')
    prepopulated_fields = {'slug': ('nombre',)}

@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'peluqueria', 'precio', 'duracion')

@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'apellido', 'peluqueria')
    # AQUÍ ESTÁ LA MAGIA: Incrustamos la tabla de horarios
    inlines = [HorarioInline]

@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    list_display = ('cliente_nombre', 'peluqueria', 'empleado', 'fecha_hora_inicio', 'estado')
    list_filter = ('estado', 'peluqueria', 'fecha_hora_inicio') # Filtros útiles en la barra lateral

admin.site.register(PerfilUsuario)
# Ya no hace falta registrar HorarioSemanal por separado porque ya sale dentro de Empleado