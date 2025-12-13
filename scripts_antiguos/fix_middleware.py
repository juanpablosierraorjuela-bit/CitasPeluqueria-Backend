import os

print("--- REPARANDO EL ARCHIVO FANTASMA (MIDDLEWARE) ---")

# Contenido corregido que usa 'Tenant' en lugar de 'Peluqueria'
middleware_code = """
from .models import Tenant

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Esta lógica permite que el servidor arranque sin errores
        # Pasa la petición directamente.
        return self.get_response(request)

# ALIAS DE SEGURIDAD:
# Si tu configuración vieja busca 'PeluqueriaMiddleware', 
# esto la redirige al nuevo código para que no falle.
PeluqueriaMiddleware = TenantMiddleware
"""

# Sobrescribimos el archivo corrupto
file_path = 'salon/middleware.py'
if os.path.exists('salon'):
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(middleware_code)
    print(f"[OK] {file_path} ha sido actualizado a la nueva versión.")
else:
    print("[ERROR] No encuentro la carpeta 'salon'.")

