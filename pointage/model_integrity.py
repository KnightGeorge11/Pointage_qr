"""Garde-fous d'intégrité sur les helpers métier des modèles.

Ces protections complètent les contraintes DB sans déplacer la logique métier
centrale hors des services existants.
"""

from datetime import timedelta

from django.utils import timezone

from .models import Employe, Pointage


def _employee_present_today(self):
    today = timezone.localtime(timezone.now()).date()
    return self.pointages.filter(
        date_pointage=today,
        heure_arrivee__isnull=False,
    ).exists()


def _employee_day_status(self, date=None):
    if date is None:
        date = timezone.localtime(timezone.now()).date()

    statut = {
        'date': date,
        'employe': {
            'id': self.id,
            'nom_complet': self.get_nom_complet(),
            'matricule': self.matricule,
            'poste': self.poste.nom if self.poste else None,
        },
        'matin': {'present': False, 'heure_arrivee': None, 'heure_depart': None, 'site': None},
        'apres_midi': {'present': False, 'heure_arrivee': None, 'heure_depart': None, 'site': None},
        'nuit': {'present': False, 'heure_arrivee': None, 'heure_depart': None, 'site': None, 'type_journee': None},
    }

    for pointage in self.pointages.filter(date_pointage=date).select_related('site'):
        if pointage.heure_arrivee is None:
            continue
        bucket = statut.get(pointage.periode)
        if bucket is None:
            continue
        bucket.update({
            'present': True,
            'heure_arrivee': pointage.heure_arrivee,
            'heure_depart': pointage.heure_depart,
            'site': pointage.site.nom if pointage.site else None,
        })
        if pointage.periode == 'nuit':
            bucket['type_journee'] = pointage.type_journee

    return statut


def _install_pointage_save_guard():
    """Protège la validation RH des heures supplémentaires.

    Une autorisation RH porte sur le montant calculé au moment de la
    validation. Si une donnée de calcul change, l'autorisation est révoquée.
    Et surtout, un environnement sans le trigger PostgreSQL doit avoir le même
    comportement : aucune H.Supp non autorisée ne doit rester persistée.
    """
    if getattr(Pointage, '_overtime_input_guard_installed', False):
        return

    original_save = Pointage.save

    def guarded_save(self, *args, **kwargs):
        if self.pk and self.heures_supplementaires_autorisees:
            try:
                previous = Pointage.objects.get(pk=self.pk)
            except Pointage.DoesNotExist:
                previous = None

            if previous is not None:
                inputs_changed = any([
                    previous.date_pointage != self.date_pointage,
                    previous.periode != self.periode,
                    previous.heure_arrivee != self.heure_arrivee,
                    previous.heure_depart != self.heure_depart,
                    previous.site_id != self.site_id,
                ])
                if inputs_changed:
                    self.heures_supplementaires_autorisees = False
                    self.heures_supplementaires_autorisees_par = None
                    self.date_autorisation_heures_supplementaires = None
                    self.motif_autorisation_heures_supplementaires = (
                        "Autorisation H.Supp révoquée automatiquement : "
                        "les données du pointage ont été modifiées."
                    )

        # Parité de sécurité avec le trigger PostgreSQL : le montant stocké
        # n'est payable/comptable que si une validation RH existe.
        if not self.heures_supplementaires_autorisees:
            self.heures_supplementaires = timedelta(0)

        return original_save(self, *args, **kwargs)

    Pointage.save = guarded_save
    Pointage._overtime_input_guard_installed = True


def install():
    Employe.est_present_aujourdhui = _employee_present_today
    Employe.get_statut_journee = _employee_day_status
    Employe._model_integrity_hardened = True
    _install_pointage_save_guard()


install()
