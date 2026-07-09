from django import template
import datetime

register = template.Library()

@register.filter
def timedelta_format(td):
    """Formate un timedelta en 'XhXX'"""
    if td and isinstance(td, datetime.timedelta):
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h{minutes:02d}"
    return "0h00"

@register.filter
def timedelta_to_time(td):
    """Convertit un timedelta en objet time pour le filtre time:"""
    if td and isinstance(td, datetime.timedelta):
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return datetime.time(hour=hours, minute=minutes)
    return datetime.time(0, 0)

@register.filter
def get_scan_by_type(scans, scan_type):
    """Récupère un scan spécifique par type"""
    if not scans:
        return None
    for scan in scans:
        if scan.type_scan == scan_type:
            return scan
    return None

@register.filter
def format_heure(value):
    """Formate un objet time ou retourne la valeur telle quelle"""
    if value is None:
        return "-"
    # Si c'est déjà une chaîne (comme "-" de default), on la retourne
    if isinstance(value, str):
        return value
    # Si c'est un objet time, on le formate
    if isinstance(value, datetime.time):
        return value.strftime('%H:%M')
    # Pour tout autre type, on tente de le convertir en chaîne
    return str(value)

@register.filter
def modulo(value, arg):
    """Filtre modulo"""
    try:
        return int(value) % arg
    except (ValueError, TypeError):
        return 0

@register.filter
def intdiv(value, arg):
    """Division entière"""
    try:
        return int(value) // arg
    except (ValueError, TypeError):
        return 0