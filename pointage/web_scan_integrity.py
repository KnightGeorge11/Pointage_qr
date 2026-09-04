"""Garde-fous de cohérence pour les vues Web de pointage.

Le scanner Web supporte volontairement deux modes d'identification :
- lecture d'un QR physique contenant matricule + token ;
- saisie ou lecture d'un matricule par le scanner USB / poste RH.

Dans les deux cas, la vue métier convertit ensuite l'identification en
couple matricule + qr_code_token avant d'appeler ``process_scan``. Ce module
ne doit donc jamais désactiver le mode matricule.

Le calcul du statut journalier est délégué au helper métier installé sur
``Employe`` afin d'éviter plusieurs implémentations concurrentes.
"""

from . import views


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


_install_presence_helper_guard()
