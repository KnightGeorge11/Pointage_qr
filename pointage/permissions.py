"""Permissions Web centralisées pour les fonctions RH/administration."""

from functools import wraps
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden


def is_rh(user):
    return bool(
        user and user.is_authenticated
        and (user.is_superuser or getattr(user, "role", None) == "admin")
    )


def rh_required(view_func):
    """Protège une vue Web RH, indépendamment des liens affichés dans l'UI."""
    @wraps(view_func)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not is_rh(request.user):
            return HttpResponseForbidden("Accès réservé au personnel RH.")
        return view_func(request, *args, **kwargs)
    return wrapped
