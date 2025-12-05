# salon/context_processors.py

def tenant_context(request):
    """
    Inyecta el objeto 'current_tenant' a todas las plantillas.
    """
    if request.user.is_authenticated and hasattr(request.user, 'peluqueria'):
        return {'current_tenant': request.user.peluqueria}
    return {}