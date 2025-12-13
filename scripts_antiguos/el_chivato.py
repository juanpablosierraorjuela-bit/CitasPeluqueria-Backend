import os
import sys
import django

# 1. Configurar entorno
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'salon_project.settings')

print("\n🕵️ --- INICIANDO DIAGNÓSTICO (EL CHIVATO) --- 🕵️")

try:
    print("�� PASO 1: Cargando el cerebro de Django (setup)...")
    django.setup()
    print("✅ [OK] Django inició correctamente. No hay errores de sintaxis graves.")
except Exception as e:
    print("\n❌ [ERROR FATAL EN EL ARRANQUE]")
    print("Aquí está el culpable. Copia este error y envíamelo:")
    print("-" * 30)
    print(e)
    print("-" * 30)
    sys.exit(1)

try:
    print("\n👉 PASO 2: Verificando Modelos y Base de Datos...")
    from salon.models import Tenant, Professional
    print(f"✅ [OK] Modelos cargados. Hay {Tenant.objects.count()} negocios registrados.")
except Exception as e:
    print(f"\n❌ [ERROR EN MODELOS] Algo falla al leer la base de datos:\n{e}")
except ImportError as e:
    print(f"\n❌ [ERROR DE IMPORTACIÓN] Estás llamando a un modelo viejo que ya no existe:\n{e}")

try:
    print("\n👉 PASO 3: Verificando Archivos 'Fantasma' (Middleware)...")
    from django.conf import settings
    middlewares = settings.MIDDLEWARE
    print(f"✅ [OK] Middlewares cargados: {len(middlewares)}")
except Exception as e:
    print(f"\n❌ [ERROR EN CONFIGURACIÓN] Revisa settings.py:\n{e}")

print("\n🏁 --- FIN DEL DIAGNÓSTICO --- 🏁\n")
