"""Garde-fous complémentaires pour les helpers de l'API mobile.

Ce module corrige uniquement les incohérences de lecture qui pourraient
faire croire à l'application qu'une garde planifiée est déjà commencée.
La création réelle des pointages reste exclusivement dans process_scan().
"""

import json

from django.http import JsonResponse
from django.utils import timezone

from . import views_mobile
from .models import Employe, Pointage, Site
from .services import parse_qr_data


def _install_next_scan_guard():
    view = views_mobile.MobileCheckFirstScanAPIView
    if getattr(view, "_next_scan_integrity_installed", False):
        return

    original_post = view.post

    def guarded_post(self, request, *args, **kwargs):
        response = original_post(self, request, *args, **kwargs)

        if response.status_code != 200:
            return response

        try:
            payload = json.loads(response.content.decode("utf-8"))
        except (TypeError, ValueError):
            return response

        data = payload.get("data") or {}
        if data.get("prochain_scan") != "fin_garde":
            return response

        # L'ancienne requête considère toute ligne nuit ouverte comme une
        # garde en cours. Or le planning utilise précisément une ligne nuit
        # avec heure_arrivee NULL. Une réservation ne constitue pas une
        # présence et ne doit pas demander une "fin de garde".
        garde = data.get("garde_en_cours") or {}
        if garde.get("heure_arrivee") not in (None, "None", ""):
            return response

        raw_qr = (request.data.get("employee_qr") or "").strip()
        parsed = parse_qr_data(raw_qr) if raw_qr else None
        if not parsed:
            return response

        try:
            employe = Employe.objects.get(
                matricule=parsed["matricule"],
                qr_code_token=parsed["token"],
                actif=True,
            )
        except Employe.DoesNotExist:
            return response

        now = timezone.localtime(timezone.now())
        garde_planifiee = Pointage.objects.filter(
            employe=employe,
            date_pointage=now.date(),
            periode="nuit",
            type_journee="garde",
            heure_arrivee__isnull=True,
            heure_depart__isnull=True,
        ).first()

        if not garde_planifiee:
            return response

        site_id = request.data.get("site_id")
        try:
            site = Site.objects.get(id=int(site_id))
        except (TypeError, ValueError, Site.DoesNotExist):
            return response

        return JsonResponse({
            "status": "success",
            "data": {
                "prochain_scan": "debut_garde",
                "mode_attendu": "garde",
                "employe": views_mobile._employe_dict(employe),
                "site": {"id": site.id, "nom": site.nom},
            },
        })

    view.post = guarded_post
    view._next_scan_integrity_installed = True


_install_next_scan_guard()
