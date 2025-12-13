import os
import django
from django.db import connection

# Configuración manual de entorno
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'salon_project.settings')
django.setup()

print("🛠️ INICIANDO REPARACIÓN TOTAL DE LA BASE DE DATOS...")

def columna_existe(tabla, columna):
    with connection.cursor() as cursor:
        descripcion = connection.introspection.get_table_description(cursor, tabla)
        nombres_columnas = [col.name for col in descripcion]
        return columna in nombres_columnas

def agregar_columna_si_falta(tabla, columna, tipo_sql):
    if not columna_existe(tabla, columna):
        print(f"  ⚠️ Falta '{columna}'. Creándola...")
        with connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo_sql};")
        print(f"  ✅ Columna '{columna}' CREADA.")
    else:
        print(f"  ✅ '{columna}' ya existe.")

# --- REPARACIÓN MASIVA DE EMPLEADO ---
print("\n1. Verificando tabla 'salon_empleado' (TODOS LOS CAMPOS)...")

# Campos básicos
agregar_columna_si_falta('salon_empleado', 'es_independiente', 'BOOLEAN DEFAULT 0')
agregar_columna_si_falta('salon_empleado', 'es_domiciliario', 'BOOLEAN DEFAULT 0')

# Campos de credenciales (LOS QUE TE ESTÁN FALLANDO AHORA)
agregar_columna_si_falta('salon_empleado', 'bold_api_key', 'VARCHAR(255) NULL')
agregar_columna_si_falta('salon_empleado', 'bold_secret_key', 'VARCHAR(255) NULL')
agregar_columna_si_falta('salon_empleado', 'telegram_token', 'VARCHAR(200) NULL')
agregar_columna_si_falta('salon_empleado', 'telegram_chat_id', 'VARCHAR(100) NULL')

# --- REPARACIÓN DE CITA ---
print("\n2. Verificando tabla 'salon_cita'...")
agregar_columna_si_falta('salon_cita', 'referencia_pago', 'VARCHAR(100) NULL')

print("\n🚀 ¡REPARACIÓN COMPLETA! INTENTA ENTRAR A EQUIPO AHORA.")
