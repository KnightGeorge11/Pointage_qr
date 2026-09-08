"""Routage explicite des notifications de l'application Web.

Le endpoint Web ne doit jamais fabriquer de liens /admin/. Jazzmin possède
son propre endpoint et réécrit uniquement ses propres notifications vers
l'espace d'administration.
"""

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse

from . import views


@login_required
def notifications_api(request):
    """Retourne des notifications Web sans exposer les anomalies RH aux comptes normaux."""
    response = views.notifications_api(request)
    if response.status_code != 200:
        return response

    try:
        data = json.loads(response.content.decode("utf-8"))
    except (TypeError, ValueError):
        return JsonResponse({"notifications": [], "count": 0})

    notifications = data.get("notifications", [])

    # Les anomalies de pointage sont des dossiers RH. Un compte standard ne
    # doit ni voir leur contenu ni recevoir un lien vers leur workflow.
    if not request.user.is_staff:
        notifications = [
            item for item in notifications
            if item.get("type") != "anomalie"
        ]

    for item in notifications:
        if item.get("type") == "anomalie":
            anomaly_id = item.get("anomalie_id")
            if anomaly_id:
                item["url"] = reverse("alerte_detail", args=[anomaly_id])
            else:
                item["url"] = reverse("alertes_rh")

    data["notifications"] = notifications
    data["count"] = len(notifications)
    return JsonResponse(data)
