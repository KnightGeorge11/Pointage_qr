# pointage/templatetags/pointage_filters.py

from django import template
from datetime import timedelta

register = template.Library()

@register.filter
def timedelta_format(value):
    """
    Formate un objet timedelta en format lisible :
    - 2j 14h55
    - 45min
    - 1h30
    """
    if not value:
        return "0h00"
    
    if isinstance(value, str):
        return value
    
    if not isinstance(value, timedelta):
        return str(value)
    
    total_seconds = int(value.total_seconds())
    if total_seconds < 0:
        total_seconds = 0
    
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    
    parts = []
    if days > 0:
        parts.append(f"{days}j")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or (hours == 0 and days == 0):
        parts.append(f"{minutes:02d}min")
    
    if not parts:
        return "0h00"
    
    return " ".join(parts)


@register.filter
def timedelta_short(value):
    """
    Format court pour les durées (ex: 2j14h)
    """
    if not value:
        return "0h"
    
    if isinstance(value, str):
        return value
    
    if not isinstance(value, timedelta):
        return str(value)
    
    total_seconds = int(value.total_seconds())
    if total_seconds < 0:
        total_seconds = 0
    
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    
    if days > 0:
        return f"{days}j{hours}h"
    elif hours > 0:
        return f"{hours}h{minutes:02d}"
    else:
        return f"{minutes}min"