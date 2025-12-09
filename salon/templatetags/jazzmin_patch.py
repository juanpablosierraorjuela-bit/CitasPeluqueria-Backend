from django import template

register = template.Library()

@register.filter
def length_is(value, arg):
    """
    Revive el filtro length_is eliminado en Django 5.1
    para compatibilidad con Jazzmin.
    """
    try:
        return len(value) == int(arg)
    except (ValueError, TypeError):
        return ""
