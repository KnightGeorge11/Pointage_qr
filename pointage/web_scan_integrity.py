"""Garde-fous de sécurité/cohérence pour les vues Web de pointage.

Le scanner Web doit utiliser le QR physique comme preuve d'identité de
l'employé. Le matricule seul ne doit jamais être transformé côté serveur en
qr_code_token.

Le calcul du statut journalier est délégué au helper métier durci installé
sur ``Employe`` afin d'éviter plusieurs implémentations concurrentes de la
même règle de présence.
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
    """Utilise une seule source métier pour le statut journalier."""
    if getattr(views.get_statut_employe_journee, "_model_status_integrity_installed", False):
        return

    def guarded_helper(employe, date_courante):
        return employe.get_statut_journee(date_courante)

    guarded_helper.__name__ = "get_statut_employe_journee"
    guarded_helper.__doc__ = (
        "Délègue le calcul du statut journalier au helper métier durci d'Employe."
    )
    guarded_helper._model_status_integrity_installed = True
    views.get_statut_employe_journee = guarded_helper


_install_web_scanner_guard()
_install_presence_helper_guard()
