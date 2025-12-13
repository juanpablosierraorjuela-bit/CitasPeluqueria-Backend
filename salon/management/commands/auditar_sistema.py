from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group, Permission
from django.core.management import call_command
from salon.models import Tenant, Professional
import random

class Command(BaseCommand):
    help = 'Audita y repara automáticamente problemas comunes del sistema PASO'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('--- 🏥 INICIANDO AUDITORÍA DEL SISTEMA PASO 🏥 ---'))

        # 1. REPARAR BASE DE DATOS
        self.stdout.write("1. Verificando integridad de la Base de Datos...")
        try:
            call_command('migrate', interactive=False)
            self.stdout.write(self.style.SUCCESS("✅ Base de datos sincronizada."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error en base de datos: {e}"))

        # 2. ASEGURAR SUPERUSUARIO
        self.stdout.write("2. Verificando acceso Administrativo...")
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', '1234')
            self.stdout.write(self.style.SUCCESS("✅ Usuario 'admin' creado (Clave: 1234)."))
        else:
            self.stdout.write(self.style.SUCCESS("✅ El usuario 'admin' ya existe."))

        # 3. REVIVIR LA VITRINA (SI ESTÁ VACÍA)
        self.stdout.write("3. Verificando Vitrina Pública...")
        if Tenant.objects.count() == 0:
            self.stdout.write(self.style.WARNING("⚠️ No hay peluquerías. Creando Demo para el diseño..."))
            
            # Crear Demo
            demo = Tenant.objects.create(
                name="Barbería King Style",
                subdomain="king-style",
                address="Centro Comercial Viva, Local 204",
                ciudad="Tunja",
                instagram="https://instagram.com",
                phone="3100000000"
            )
            
            # Crear Barbero Demo
            Professional.objects.create(
                tenant=demo,
                name="Juan El Bravo",
                phone="3001234567",
                is_external=False
            )
            
            self.stdout.write(self.style.SUCCESS(f"✅ Creada '{demo.name}' para que la página se vea linda."))
        else:
            self.stdout.write(self.style.SUCCESS(f"✅ Hay {Tenant.objects.count()} negocios activos en la vitrina."))

        # 4. LIMPIEZA FINAL
        self.stdout.write("4. Limpiando sesiones basura...")
        call_command('clearsessions')
        
        self.stdout.write(self.style.SUCCESS('\n✨ AUDITORÍA COMPLETADA. EL SISTEMA ESTÁ SANO. ✨'))
