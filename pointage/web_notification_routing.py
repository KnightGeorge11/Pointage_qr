"""Routage explicite des notifications de l'application Web.

Le endpoint Web ne doit jamais fabriquer ni conserver de lien /admin/.
Jazzmin possède son propre endpoint et réécrit uniquement ses notifications
vers l'espace d'administration.
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
        notification_type = item.get("type")

        # Une notification d'anomalie ouverte doit rester dans l'application
        # Web, même si une ancienne version de views.py fournit encore un
        # lien /admin/.
        if notification_type == "anomalie":
            anomaly_id = item.get("anomalie_id")
            item["url"] = (
                reverse("alerte_detail", args=[anomaly_id])
                if anomaly_id
                else reverse("alertes_rh")
            )
            continue

        # Les demandes ont historiquement reçu directement une URL Jazzmin
        # depuis views.notifications_api(). C'est précisément ce qu'il faut
        # empêcher sur le site Web. Il n'existe pas de page Web de traitement
        # des demandes : on reste donc dans l'application et on affiche les
        # pointages, sans exposer /admin/ au navigateur Web.
        if notification_type == "demande_en_attente":
            item["url"] = reverse("pointages")
            continue

        # Défense en profondeur : aucune notification servie par cet endpoint
        # ne doit pouvoir faire sortir l'utilisateur du périmètre Web.
        url = item.get("url") or ""
        if isinstance(url, str) and url.startswith("/admin/"):
            item["url"] = reverse("dashboard")

    data["count"] = len(data.get("notifications", []))
    return JsonResponse(data)
