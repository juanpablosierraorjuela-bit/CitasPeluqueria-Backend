# salon/middleware.py

from django_multitenant.utils import set_current_tenant
from .models import Peluqueria # Asume que Peluqueria ya existe

class PeluqueriaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                # Le dice a la librería cuál es el inquilino actual basado en el usuario
                current_peluqueria = request.user.peluqueria
                set_current_tenant(current_peluqueria)
            except AttributeError:
                # Manejar usuarios que no están asignados a una peluquería
                set_current_tenant(None)
        else:
            set_current_tenant(None)

        response = self.get_response(request)

        # Limpiar el contexto después de la solicitud
        set_current_tenant(None)

        return response