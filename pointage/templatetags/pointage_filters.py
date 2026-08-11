# pointage/templatetags/pointage_filters.py

from django import template
from datetime import timedelta

register = template.Library()

@register.filter
def timedelta_format(value):
    """Formate un timedelta en HHhMM ou Xj XhXX"""
    if not value:
        return "0h00"
    if isinstance(value, timedelta):
        total_secondes = int(value.total_seconds())
        jours = total_secondes // 86400
        heures = (total_secondes % 86400) // 3600
        minutes = (total_secondes % 3600) // 60
        
        if jours > 0:
            return f"{jours}j {heures}h{minutes:02d}"
        return f"{heures}h{minutes:02d}"
    return str(value)