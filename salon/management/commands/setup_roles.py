from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from salon.models import Cita, Servicio, Empleado, Peluqueria

class Command(BaseCommand):
    help = 'Configura los Grupos y Permisos iniciales del sistema SaaS'

    def handle(self, *args, **kwargs):
        self.stdout.write("Configurando roles de seguridad...")

        # 1. Permisos para el DUEÑO (Administrador de su local)
        # Puede gestionar todo su negocio, pero no puede borrar la peluquería (eso lo haces tú)
        permisos_dueno = [
            # Empleados
            'view_empleado', 'add_empleado', 'change_empleado', 'delete_empleado',
            # Servicios
            'view_servicio', 'add_servicio', 'change_servicio', 'delete_servicio',
            # Citas
            'view_cita', 'add_cita', 'change_cita', 'delete_cita',
            # Peluquería (Solo ver y editar datos básicos, no borrar)
            'view_peluqueria', 'change_peluqueria',
        ]

        # 2. Permisos para el ESTILISTA (Empleado)
        # Solo necesita ver citas y marcarlas (editar estado)
        permisos_estilista = [
            'view_cita', 'change_cita', 
            'view_servicio', # Para ver qué servicio le toca hacer
        ]

        # --- FUNCIÓN AUXILIAR PARA ASIGNAR ---
        def asignar_permisos(nombre_grupo, lista_permisos):
            grupo, created = Group.objects.get_or_create(name=nombre_grupo)
            contador = 0
            for codename in lista_permisos:
                try:
                    # Buscamos el permiso asegurando que sea de la app 'salon'
                    perm = Permission.objects.get(codename=codename, content_type__app_label='salon')
                    grupo.permissions.add(perm)
                    contador += 1
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"⚠️ Permiso no encontrado: {codename}"))
            
            accion = "Creando" if created else "Actualizando"
            self.stdout.write(self.style.SUCCESS(f"✅ {accion} Grupo '{nombre_grupo}': {contador} permisos asignados."))

        # EJECUTAR
        asignar_permisos('Dueños', permisos_dueno)
        asignar_permisos('Estilistas', permisos_estilista)

        self.stdout.write(self.style.SUCCESS("🎉 ¡Configuración de roles completada con éxito!"))
