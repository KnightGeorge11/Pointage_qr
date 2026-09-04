"""Garde-fous d'integrite pour la classification des anomalies.

La classification metier est centralisee dans anomalies.py. Ce module veille
cependant a ce qu'un AnomaliePointage cree par un autre chemin (admin, script,
import ou code legacy) conserve toujours les memes marqueurs canoniques.
"""

from .models import AnomaliePointage
from .anomalies import (
    categorie_anomalie,
    anomalie_est_bloquante,
    anomalie_necessite_traitement_rh,
)


def install():
    if getattr(AnomaliePointage, '_classification_integrity_installed', False):
        return

    original_save = AnomaliePointage.save

    def guarded_save(self, *args, **kwargs):
        contexte = dict(self.contexte or {})
        contexte['categorie'] = categorie_anomalie(self.type)
        contexte['bloquante'] = anomalie_est_bloquante(self.type)
        contexte['traitement_rh_requis'] = anomalie_necessite_traitement_rh(self.type)
        self.contexte = contexte
        return original_save(self, *args, **kwargs)

    AnomaliePointage.save = guarded_save
    AnomaliePointage._classification_integrity_installed = True


install()
