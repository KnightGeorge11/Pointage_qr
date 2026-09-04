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
    """Retourne des notifications dont les liens restent exclusivement Web."""
    response = views.notifications_api(request)
    if response.status_code != 200:
        return response

    try:
        data = json.loads(response.content.decode("utf-8"))
    except (TypeError, ValueError):
        return JsonResponse({"notifications": [], "count": 0})

    for item in data.get("notifications", []):
        if item.get("type") == "anomalie":
            anomaly_id = item.get("anomalie_id")
            if anomaly_id:
                item["url"] = reverse("alerte_detail", args=[anomaly_id])
            else:
                # Compatibilité avec les anciennes notifications sans ID.
                item["url"] = reverse("alertes_rh")

    data["count"] = len(data.get("notifications", []))
    return JsonResponse(data)
