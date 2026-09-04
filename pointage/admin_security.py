"""Garde-fous pour les endpoints exclusivement destinés au RH."""

import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.decorators import action

from . import views
from .models import Employe, Pointage, AnomaliePointage


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


def _attach_exact_anomaly_admin_urls(data):
    """Associe chaque notification d'anomalie à son panneau de workflow admin."""
    anomaly_items = [
        item for item in data.get("notifications", [])
        if item.get("type") == "anomalie"
    ]
    if not anomaly_items:
        return data

    anomalies = list(
        AnomaliePointage.objects.filter(
            statut=AnomaliePointage.STATUT_OUVERTE
        ).select_related("employe").order_by("-created_at", "-pk")
    )

    by_message = {}
    for anomaly in anomalies:
        qui = anomaly.employe.get_nom_complet() if anomaly.employe else (anomaly.matricule_scanne or '?')
        message = f"Anomalie ({anomaly.get_type_display()}) — {qui}"
        by_message.setdefault(message, []).append(anomaly)

    used_ids = set()
    for item in anomaly_items:
        candidates = by_message.get(item.get("message"), [])
        candidate = next((a for a in candidates if a.pk not in used_ids), None)
        if candidate is None:
            continue
        used_ids.add(candidate.pk)
        item["anomalie_id"] = candidate.pk
        item["url"] = f"/admin/pointage/anomaliepointage/{candidate.pk}/workflow/"

    return data


def notifications_api(request, *args, **kwargs):
    response = views.notifications_api(request, *args, **kwargs)

    if response.status_code != 200:
        return response

    try:
        data = json.loads(response.content.decode("utf-8"))
    except (TypeError, ValueError):
        return JsonResponse({"notifications": [], "count": 0})

    if _is_rh(request.user):
        data = _attach_exact_anomaly_admin_urls(data)
        return JsonResponse(data)

    notifications = [
        item for item in data.get("notifications", [])
        if item.get("type") != "anomalie"
    ]
    return JsonResponse({"notifications": notifications, "count": len(notifications)})


def _secure_api_function(function):
    """Applique la permission RH au vrai wrapper DRF, sans remplacer celui-ci."""
    view_class = getattr(function, "cls", None)
    if view_class is not None:
        view_class.permission_classes = [IsRHPermission]
    return function


@action(detail=False, methods=['get'])
def statistiques(self, request):
    """Statistiques RH : une réservation de garde n'est pas une présence."""
    today = timezone.localtime(timezone.now()).date()
    total_employes = Employe.objects.filter(actif=True).count()
    today_attendance = Pointage.objects.filter(
        date_pointage=today,
        heure_arrivee__isnull=False,
    )
    presents = today_attendance.values('employe').distinct().count()
    return Response({
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
    })


def _deny_pointage_create_api(self, request, *args, **kwargs):
    """Le pointage ne peut jamais être créé directement par l'API REST."""
    return Response(
        {"detail": "Création directe interdite. Utilisez le flux de scan QR."},
        status=405,
    )


def secure_sensitive_apis():
    """Sécurise les endpoints sensibles sans écraser les permissions de lecture."""
    pointage_viewset = getattr(views, "PointageViewSet", None)
    if pointage_viewset is not None:
        pointage_viewset.statistiques = statistiques
        pointage_viewset.create = _deny_pointage_create_api

    sensitive_functions = (
        "employe_qr_data",
        "get_statut_journee",
        "get_prochain_scan",
        "get_dashboard_stats",
        "get_charts_data",
    )
    for name in sensitive_functions:
        function = getattr(views, name, None)
        if function is not None:
            _secure_api_function(function)


@login_required
def scanner_view(request, *args, **kwargs):
    """Pointage Web : le matricule seul est une identification valide."""
    return views.scanner_view(request, *args, **kwargs)


class RHAnomaliePointageViewSet(views.AnomaliePointageViewSet):
    permission_classes = [IsRHPermission]


secure_sensitive_apis()
