"""Garde-fous de sécurité pour le scanner Web.

Le scanner Web doit utiliser le QR physique comme preuve d'identité de
l'employé. Le matricule seul est une donnée publique/devinable et ne doit
jamais être transformé côté serveur en qr_code_token.

Ce module conserve les vues existantes intactes et bloque uniquement les
raccourcis qui contournent le badge ou confondent une garde planifiée avec une
présence réelle. Les scans QR valides continuent de passer par process_scan().
"""

from django.contrib import messages
from django.shortcuts import redirect

from . import views


def _install_web_scanner_guard():
    view = views.scanner_view
    if getattr(view, "_qr_only_integrity_installed", False):
        return

    original_view = view

    def guarded_scanner_view(request, *args, **kwargs):
        if request.method == "POST":
            raw_qr = (request.POST.get("qr_data") or "").strip()
            matricule = (request.POST.get("matricule") or "").strip()

            # Le matricule seul ne constitue jamais une authentification.
            # L'ancienne branche construisait elle-même le token QR à partir
            # du matricule, ce qui permettait à n'importe quel utilisateur
            # connecté de pointer un autre employé sans scanner son badge.
            if not raw_qr and matricule:
                messages.error(
                    request,
                    "❌ Pointage refusé : veuillez scanner le QR code du badge. "
                    "Le matricule seul n'est pas accepté.",
                )
                return redirect("scanner")

        return original_view(request, *args, **kwargs)

    guarded_scanner_view.__name__ = getattr(original_view, "__name__", "scanner_view")
    guarded_scanner_view.__doc__ = getattr(original_view, "__doc__", None)
    guarded_scanner_view._qr_only_integrity_installed = True
    views.scanner_view = guarded_scanner_view


def _install_presence_helper_guard():
    """Une ligne de garde planifiée sans arrivée n'est pas une présence."""
    original_helper = views.get_statut_employe_journee
    if getattr(original_helper, "_planned_guard_integrity_installed", False):
        return

    def guarded_helper(employe, date_courante):
        statut = original_helper(employe, date_courante)
        pointages = employe.pointages.filter(date_pointage=date_courante)

        for periode in ("matin", "apres_midi", "nuit"):
            pointage = pointages.filter(periode=periode).first()
            if pointage is None or pointage.heure_arrivee is None:
                statut[periode]["present"] = False

        return statut

    guarded_helper.__name__ = getattr(original_helper, "__name__", "get_statut_employe_journee")
    guarded_helper.__doc__ = getattr(original_helper, "__doc__", None)
    guarded_helper._planned_guard_integrity_installed = True
    views.get_statut_employe_journee = guarded_helper


def _install_api_day_status_guard():
    """L'endpoint de statut ne doit pas compter une réservation de garde."""
    view = views.get_statut_journee
    if getattr(view, "_planned_guard_integrity_installed", False):
        return

    original_view = view

    def guarded_status(request, employe_id, *args, **kwargs):
        response = original_view(request, employe_id, *args, **kwargs)
        if getattr(response, "status_code", 500) != 200:
            return response

        try:
            payload = response.data if hasattr(response, "data") else None
            if payload is None:
                return response

            for periode in ("matin", "apres_midi", "nuit"):
                bucket = payload.get(periode)
                if not bucket:
                    continue
                if bucket.get("heure_arrivee") in (None, "None", ""):
                    bucket["present"] = False
        except Exception:
            # Ce garde-fou ne doit jamais casser un endpoint de lecture.
            return response

        return response

    guarded_status.__name__ = getattr(original_view, "__name__", "get_statut_journee")
    guarded_status.__doc__ = getattr(original_view, "__doc__", None)
    guarded_status._planned_guard_integrity_installed = True
    views.get_statut_journee = guarded_status


_install_web_scanner_guard()
_install_presence_helper_guard()
_install_api_day_status_guard()
