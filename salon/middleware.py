cat <<EOF > salon/middleware.py
from django_multitenant.utils import set_current_tenant
from .models import Peluqueria

class PeluqueriaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Lógica protegida: verifica usuario, perfil y peluquería antes de asignar tenant
        if request.user.is_authenticated and hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
            set_current_tenant(request.user.perfil.peluqueria)
        else:
            set_current_tenant(None)
        
        response = self.get_response(request)
        set_current_tenant(None)
        return response
EOF
