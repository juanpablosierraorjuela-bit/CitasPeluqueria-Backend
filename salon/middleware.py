from django_multitenant.utils import set_current_tenant
from .models import Peluqueria

class PeluqueriaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # VERIFICACIÓN SEGURA: Primero miramos si tiene perfil, y luego si tiene peluquería
            if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
                set_current_tenant(request.user.perfil.peluqueria)
            else:
                # Si es superusuario o no tiene peluquería asignada
                set_current_tenant(None)
        else:
            set_current_tenant(None)

        response = self.get_response(request)
        
        # Limpieza final
        set_current_tenant(None)
        return response
