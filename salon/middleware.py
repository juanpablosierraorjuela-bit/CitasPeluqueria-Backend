from django_multitenant.utils import set_current_tenant
from .models import Peluqueria

class PeluqueriaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Lógica de seguridad:
        # 1. Verifica si el usuario está autenticado
        # 2. Verifica si el objeto 'user' tiene el atributo 'perfil' y luego 'peluqueria'
        if request.user.is_authenticated and hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
            set_current_tenant(request.user.perfil.peluqueria)
        else:
            set_current_tenant(None)

        response = self.get_response(request)
        
        # Limpieza final
        set_current_tenant(None)
        return response
