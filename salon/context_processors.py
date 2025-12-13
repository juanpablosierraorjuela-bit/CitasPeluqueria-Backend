# UBICACIÓN: salon/context_processors.py

def tenant_context(request):
    """
    Inyecta el objeto 'current_tenant' a todas las plantillas.
    """
    tenant = None
    if request.user.is_authenticated:
        try:
            # 1. Intentar desde PerfilUsuario (Dueño - asumiendo relación tenant)
            if hasattr(request.user, 'tenants') and request.user.tenants.exists():
                tenant = request.user.tenants.first()
            
            # 2. Intentar desde Empleado (Estilista)
            elif hasattr(request.user, 'professional_profile') and request.user.professional_profile.tenant:
                tenant = request.user.professional_profile.tenant
                
        except Exception:
            pass
            
    return {'current_tenant': tenant}
