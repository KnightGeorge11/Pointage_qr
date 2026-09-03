"""Garde-fous pour les endpoints exclusivement destinés au RH."""

import json

from django.http import HttpResponseForbidden, JsonResponse
from rest_framework.permissions import BasePermission

from . import views


def _is_rh(user):
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or getattr(user, "role", None) == "admin")
    )


class IsRHPermission(BasePermission):
    """Permission DRF stricte : superuser ou rôle métier admin."""

    def has_permission(self, request, view):
        return _is_rh(request.user)


def alertes_rh_view(request, *args, **kwargs):
    """La page des anomalies est strictement réservée au RH."""
    if not _is_rh(request.user):
        return HttpResponseForbidden("Accès réservé au personnel RH.")
    return views.alertes_rh_view(request, *args, **kwargs)


def alerte_detail_view(request, *args, **kwargs):
    """Le détail et les actions sur une anomalie sont réservés au RH."""
    if not _is_rh(request.user):
        return HttpResponseForbidden("Accès réservé au personnel RH.")
    return views.alerte_detail_view(request, *args, **kwargs)


def export_resume_excel(request, *args, **kwargs):
    """L'export RH ne doit pas être accessible au simple compte staff."""
    if not _is_rh(request.user):
        return HttpResponseForbidden("Accès réservé au personnel RH.")
    return views.export_resume_excel(request, *args, **kwargs)


def admin_badge_counts_api(request, *args, **kwargs):
    """Les compteurs de sidebar ne sont jamais exposés aux comptes ordinaires."""
    if not _is_rh(request.user):
        return JsonResponse({"error": "Forbidden"}, status=403)
    return views.admin_badge_counts_api(request, *args, **kwargs)


def notifications_api(request, *args, **kwargs):
    """Les notifications d'anomalies et de demandes RH restent privées."""
    if _is_rh(request.user):
        return views.notifications_api(request, *args, **kwargs)

    # Le endpoint historique ajoute les anomalies ouvertes pour tout compte
    # authentifié. On conserve uniquement les notifications personnelles du
    # demandeur afin de ne pas divulguer les données RH des autres employés.
    response = views.notifications_api(request, *args, **kwargs)
    if response.status_code != 200:
        return response

    try:
        data = json.loads(response.content.decode("utf-8"))
    except (TypeError, ValueError):
        return JsonResponse({"notifications": [], "count": 0})

    notifications = [
        item for item in data.get("notifications", [])
        if item.get("type") != "anomalie"
    ]
    return JsonResponse({"notifications": notifications, "count": len(notifications)})


class RHAnomaliePointageViewSet(views.AnomaliePointageViewSet):
    """Version API RH : aucune lecture d'anomalies par les comptes ordinaires."""

    permission_classes = [IsRHPermission]
