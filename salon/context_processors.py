# UBICACIÓN: salon/context_processors.py

def tenant_context(request):
    """
    Inyecta el objeto 'current_tenant' a todas las plantillas de forma segura.
    Detecta si el usuario es Dueño o Empleado para mostrar la info correcta.
    """
    tenant = None
    if request.user.is_authenticated:
        try:
            # 1. Intentar desde PerfilUsuario (Dueño)
            if hasattr(request.user, 'perfil') and request.user.perfil.peluqueria:
                tenant = request.user.perfil.peluqueria
            
            # 2. Intentar desde Empleado (Estilista)
            elif hasattr(request.user, 'empleado_perfil') and request.user.empleado_perfil.peluqueria:
                tenant = request.user.empleado_perfil.peluqueria
                
        except Exception:
            # Si hay inconsistencia de datos, no rompemos la página
            pass
            
    return {'current_tenant': tenant}
