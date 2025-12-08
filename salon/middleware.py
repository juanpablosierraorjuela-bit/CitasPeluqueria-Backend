from django_multitenant.utils import set_current_tenant
from .models import Peluqueria

class PeluqueriaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Verificamos con mucho cuidado si tiene perfil y peluquería
            if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
                set_current_tenant(request.user.perfil.peluqueria)
            else:
                set_current_tenant(None)
        else:
            set_current_tenant(None)

        response = self.get_response(request)
        return response
