"""Garde-fous pour les endpoints exclusivement destinés au RH."""

import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework import status as drf_status

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


@login_required
def alertes_rh_view(request, *args, **kwargs):
    """La page des anomalies est strictement réservée au RH."""
    if not _is_rh(request.user):
        return HttpResponseForbidden("Accès réservé au personnel RH.")
    return views.alertes_rh_view(request, *args, **kwargs)


@login_required
def alerte_detail_view(request, *args, **kwargs):
    """Le détail et les actions sur une anomalie sont réservés au RH."""
    if not _is_rh(request.user):
        return HttpResponseForbidden("Accès réservé au personnel RH.")
    return views.alerte_detail_view(request, *args, **kwargs)


@login_required
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


def _rh_function_wrapper(function):
    """Protège un endpoint de données RH sans dupliquer sa logique métier."""
    def wrapped(request, *args, **kwargs):
        if not _is_rh(request.user):
            return Response(
                {"detail": "Accès réservé au personnel RH."},
                status=drf_status.HTTP_403_FORBIDDEN,
            )
        return function(request, *args, **kwargs)
    wrapped._rh_secured = True
    return wrapped


def secure_sensitive_apis():
    """Réduit l'exposition des données RH et des secrets d'identification QR.

    Les endpoints mobiles dédiés restent séparés : cette protection concerne
    les API web générales qui permettenttait auparavant à tout compte
    authentifié d'énumérer des employés/pointages ou de récupérer un token QR.
    """
    sensitive_viewsets = ("EmployeViewSet", "SiteViewSet", "PointageViewSet")
    for name in sensitive_viewsets:
        viewset = getattr(views, name, None)
        if viewset is not None:
            viewset.permission_classes = [IsRHPermission]

    sensitive_functions = (
        "employe_qr_data",
        "get_statut_journee",
        "get_prochain_scan",
        "get_dashboard_stats",
        "get_charts_data",
    )
    for name in sensitive_functions:
        function = getattr(views, name, None)
        if function is not None and not getattr(function, "_rh_secured", False):
            setattr(views, name, _rh_function_wrapper(function))


class RHAnomaliePointageViewSet(views.AnomaliePointageViewSet):
    """Version API RH : aucune lecture d'anomalies par les comptes ordinaires."""

    permission_classes = [IsRHPermission]


secure_sensitive_apis()
