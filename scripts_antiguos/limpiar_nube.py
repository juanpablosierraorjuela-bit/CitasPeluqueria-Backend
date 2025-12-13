import os
import django
from django.db import connection

# Configurar Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "salon_project.settings")
django.setup()

print("--- ☢️ INICIANDO PROTOCOLO DE LIMPIEZA NUCLEAR EN RENDER ☢️ ---")
print("ADVERTENCIA: Esto borrará todos los datos de la base de datos remota para arreglar el conflicto.")

with connection.cursor() as cursor:
    # 1. Eliminar todas las tablas del esquema público
    print("1. Eliminando tablas antiguas corruptas...")
    cursor.execute("DROP SCHEMA public CASCADE;")
    cursor.execute("CREATE SCHEMA public;")
    print("✅ Base de datos totalmente limpia.")

print("2. Reconstruyendo tablas nuevas (Migrate)...")
# Ejecutamos migrate desde el sistema
os.system("python manage.py migrate")

print("3. Creando Superusuario de Rescate...")
# Crear usuario admin automágicamente
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', '1234')
    print("✅ Usuario 'admin' (clave: 1234) creado.")
else:
    print("ℹ️ El usuario admin ya existe.")

print("\n--- 🏁 LIMPIEZA COMPLETADA. TU PÁGINA DEBERÍA VIVIR AHORA 🏁 ---")
