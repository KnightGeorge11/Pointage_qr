"""Garde-fous d'intégrité sur les helpers métier des modèles.

Ces helpers sont utilisés par plusieurs vues/clients. Une trace de garde
planifiée (date/shift créés mais sans arrivée) n'est pas une présence réelle.
"""

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
        # Une présence exige une arrivée réelle. Les placeholders de garde
        # (heure_arrivee=NULL) représentent une planification, pas une entrée.
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


def install():
    Employe.est_present_aujourdhui = _employee_present_today
    Employe.get_statut_journee = _employee_day_status
    Employe._model_integrity_hardened = True


install()
