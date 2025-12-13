# UBICACIÓN: salon/middleware.py
from django_multitenant.utils import set_current_tenant
from .models import Peluqueria

class PeluqueriaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = None
        if request.user.is_authenticated:
            try:
                # Verificar Perfil de Dueño
                if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
                    tenant = request.user.perfil.peluqueria
                # Verificar Perfil de Empleado
                elif hasattr(request.user, 'empleado_perfil') and request.user.empleado_perfil.peluqueria:
                    tenant = request.user.empleado_perfil.peluqueria
            except Exception:
                # Ignorar errores de usuarios mal configurados para permitir que cargue el admin
                pass

        set_current_tenant(tenant)
        response = self.get_response(request)
        set_current_tenant(None)
        
        return response
