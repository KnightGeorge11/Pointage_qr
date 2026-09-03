"""Garde-fous pour les endpoints exclusivement destinés au RH."""

import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework import status as drf_status
from rest_framework.decorators import action

from . import views
from .models import Employe, Pointage
from django.utils import timezone


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
    if not _is_rh(request.user):
        return HttpResponseForbidden("Accès réservé au personnel RH.")
    return views.alertes_rh_view(request, *args, **kwargs)


@login_required
def alerte_detail_view(request, *args, **kwargs):
    if not _is_rh(request.user):
        return HttpResponseForbidden("Accès réservé au personnel RH.")
    return views.alerte_detail_view(request, *args, **kwargs)


@login_required
def export_resume_excel(request, *args, **kwargs):
    if not _is_rh(request.user):
        return HttpResponseForbidden("Accès réservé au personnel RH.")
    return views.export_resume_excel(request, *args, **kwargs)


def admin_badge_counts_api(request, *args, **kwargs):
    if not _is_rh(request.user):
        return JsonResponse({"error": "Forbidden"}, status=403)
    return views.admin_badge_counts_api(request, *args, **kwargs)


def notifications_api(request, *args, **kwargs):
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
    def wrapped(request, *args, **kwargs):
        if not _is_rh(request.user):
            return Response(
                {"detail": "Accès réservé au personnel RH."},
                status=drf_status.HTTP_403_FORBIDDEN,
            )
        return function(request, *args, **kwargs)
    wrapped._rh_secured = True
    return wrapped


def _correct_pointage_statistics(self, request):
    """Statistiques RH : une réservation de garde n'est pas une présence."""
    today = timezone.localtime(timezone.now()).date()
    total_employes = Employe.objects.filter(actif=True).count()
    today_attendance = Pointage.objects.filter(
        date_pointage=today,
        heure_arrivee__isnull=False,
    )
    presents = today_attendance.values('employe').distinct().count()
    data = {
        'total_employes': total_employes,
        'presents_aujourdhui': presents,
        'absents_aujourdhui': max(0, total_employes - presents),
        'retards_aujourdhui': today_attendance.filter(
            periode__in=['matin', 'apres_midi'], retard__gt=timedelta(0)
        ).count(),
        'gardes_en_cours': Pointage.objects.filter(
            date_pointage__gte=today - timedelta(days=1),
            date_pointage__lte=today,
            periode='nuit',
            type_journee='garde',
            heure_arrivee__isnull=False,
            heure_depart__isnull=True,
        ).count(),
        'date': today,
    }
    return Response(data)


def secure_sensitive_apis():
    sensitive_viewsets = ("EmployeViewSet", "SiteViewSet", "PointageViewSet")
    for name in sensitive_viewsets:
        viewset = getattr(views, name, None)
        if viewset is not None:
            viewset.permission_classes = [IsRHPermission]

    # Corriger le endpoint de statistiques du ViewSet avant l'enregistrement
    # du routeur : l'ancienne version comptait les réservations de garde
    # (heure_arrivee=NULL) comme des présences.
    pointage_viewset = getattr(views, "PointageViewSet", None)
    if pointage_viewset is not None:
        pointage_viewset.statistiques = action(detail=False, methods=['get'])(_correct_pointage_statistics)

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


@login_required
def scanner_view(request, *args, **kwargs):
    """Le scanner Web doit recevoir le QR réel, jamais un matricule seul."""
    if request.method == "POST":
        raw_qr = (request.POST.get("qr_data") or "").strip()
        matricule = (request.POST.get("matricule") or "").strip()
        if not raw_qr and matricule:
            messages.error(
                request,
                "❌ Le pointage Web doit être effectué par lecture du QR code. "
                "Le matricule seul est refusé.",
            )
            return redirect("scanner")
    return views.scanner_view(request, *args, **kwargs)


class RHAnomaliePointageViewSet(views.AnomaliePointageViewSet):
    permission_classes = [IsRHPermission]


secure_sensitive_apis()
