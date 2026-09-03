"""Garde-fous de sécurité/cohérence pour les vues Web de pointage.

Le scanner Web doit utiliser le QR physique comme preuve d'identité de
l'employé. Le matricule seul ne doit jamais être transformé côté serveur en
qr_code_token.

Le module corrige également un helper de statut qui considérait auparavant
une ligne de garde planifiée (heure_arrivee NULL) comme une présence réelle.
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


_install_web_scanner_guard()
_install_presence_helper_guard()
