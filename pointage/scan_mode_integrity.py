"""Garde-fou central sur le mode de scan.

Le mode ``garde`` est privilégié car il permet notamment de dépasser la
plage globale 05:00–23:00. Il ne doit donc jamais être une simple option
fournie librement par le client.

Une garde est autorisée uniquement si l'employé possède :
- une garde déjà ouverte à clôturer, ou
- une garde planifiée pour la date du scan.

Le contrôle est placé autour du service central afin que les vues Web,
mobile et tout autre appel à ``process_scan`` bénéficient de la même règle.
"""

from datetime import datetime

from django.db import transaction
from django.utils import timezone

from .models import Employe, Pointage
from . import services


_INSTALL_FLAG = "_guard_mode_integrity_installed"


def _dates_candidates(captured_at):
    """Retourne les dates pertinentes sans faire confiance à l'horodatage.

    Le service central reste responsable de valider ``captured_at``. Ici,
    cette valeur ne sert qu'à retrouver une planification offline éventuelle.
    La date serveur est toujours incluse.
    """
    dates = {timezone.localtime(timezone.now()).date()}
    if isinstance(captured_at, datetime):
        if timezone.is_naive(captured_at):
            captured_at = timezone.make_aware(captured_at, timezone.get_current_timezone())
        dates.add(timezone.localtime(captured_at).date())
    return dates


def _guard_mode_authorized(employe, dates):
    """Vérifie qu'une garde réelle ou planifiée autorise le mode garde."""
    garde_ouverte = Pointage.objects.filter(
        employe=employe,
        periode="nuit",
        type_journee="garde",
        heure_arrivee__isnull=False,
        heure_depart__isnull=True,
    ).exists()
    if garde_ouverte:
        return True

    return Pointage.objects.filter(
        employe=employe,
        date_pointage__in=dates,
        periode="nuit",
        type_journee="garde",
        heure_arrivee__isnull=True,
        heure_depart__isnull=True,
    ).exists()


def _install():
    if getattr(services.process_scan, _INSTALL_FLAG, False):
        return

    original_process_scan = services.process_scan

    def guarded_process_scan(*args, **kwargs):
        mode = kwargs.get("mode", "auto")
        if len(args) >= 4:
            mode = args[3]

        if mode != "garde":
            return original_process_scan(*args, **kwargs)

        matricule = kwargs.get("matricule")
        qr_token = kwargs.get("qr_token")
        if len(args) >= 1:
            matricule = args[0]
        if len(args) >= 2:
            qr_token = args[1]

        try:
            employe = Employe.objects.get(matricule=matricule, qr_code_token=qr_token)
        except (Employe.DoesNotExist, Employe.MultipleObjectsReturned):
            # Le service central produira sa réponse standard (QR invalide).
            return original_process_scan(*args, **kwargs)

        captured_at = kwargs.get("captured_at")
        if len(args) >= 7:
            captured_at = args[6]
        dates = _dates_candidates(captured_at)

        with transaction.atomic():
            employe = Employe.objects.select_for_update().get(pk=employe.pk)
            if not _guard_mode_authorized(employe, dates):
                return {
                    "status": "warning",
                    "code": "GARDE_NON_AUTORISEE",
                    "message": (
                        "Mode garde refusé : aucune garde planifiée ou garde en cours "
                        "n'est associée à cet employé pour la date du scan."
                    ),
                }

            return original_process_scan(*args, **kwargs)

    guarded_process_scan.__name__ = getattr(original_process_scan, "__name__", "process_scan")
    guarded_process_scan.__doc__ = getattr(original_process_scan, "__doc__", None)
    setattr(guarded_process_scan, _INSTALL_FLAG, True)
    services.process_scan = guarded_process_scan


_install()
