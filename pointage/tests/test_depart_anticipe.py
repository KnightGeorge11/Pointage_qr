# pointage/tests/test_depart_anticipe.py
#
# Vérifie la détection des départs anticipés (services._detecter_depart_anticipe) :
#   - le pointage reste TOUJOURS enregistré normalement (jamais bloqué) ;
#   - une AnomaliePointage de type 'depart_anticipe' est créée quand la
#     sortie intervient nettement avant la fermeture officielle du site ;
#   - aucune anomalie n'est créée pour une sortie proche de la fermeture
#     (sous le seuil) ni pour une sortie tardive ;
#   - les gardes de nuit ne sont jamais concernées.

from datetime import time as dtime
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from pointage.models import Employe, Site, Pointage, AnomaliePointage
from pointage.services import process_scan


def _aware(date_, hh, mm):
    return timezone.make_aware(timezone.datetime.combine(date_, dtime(hh, mm)))


class DepartAnticipeTestCase(TestCase):

    def setUp(self):
        self.site = Site.objects.create(
            nom="Site Principal",
            adresse="1 Rue de Test",
            heure_ouverture_matin=dtime(8, 0),
            heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 30),
            heure_fermeture_apres_midi=dtime(17, 30),
        )
        self.employe = Employe.objects.create(
            nom="Rakoto", prenom="Jean", matricule="E001", actif=True
        )
        self.today = timezone.localtime(timezone.now()).date()

    def _scan(self, hh, mm):
        fake_now = _aware(self.today, hh, mm)
        with patch('pointage.services.timezone.now', return_value=fake_now):
            return process_scan(
                matricule=self.employe.matricule,
                qr_token=str(self.employe.qr_code_token),
                site_id=self.site.id,
            )

    def test_sortie_matin_tres_anticipee_cree_une_anomalie(self):
        """Exemple de l'énoncé : entrée 08h, sortie matin à 10h (fermeture 12h)."""
        self._scan(8, 0)
        result = self._scan(10, 0)

        # Le scan reste un succès : le pointage est enregistré normalement.
        assert result['status'] == 'success'
        assert result['code'] == 'sortie_matin'
        pointage = Pointage.objects.get(employe=self.employe, periode='matin')
        assert pointage.heure_arrivee == dtime(8, 0)
        assert pointage.heure_depart == dtime(10, 0)

        # ET une anomalie de suivi est créée en plus.
        anomalie = AnomaliePointage.objects.get(
            employe=self.employe, type=AnomaliePointage.TYPE_DEPART_ANTICIPE
        )
        assert anomalie.statut == AnomaliePointage.STATUT_OUVERTE
        assert anomalie.contexte['minutes_avance'] == 120
        assert anomalie.contexte['periode'] == 'matin'

    def test_sortie_proche_fermeture_ne_cree_pas_anomalie(self):
        """11h58 : 2 min avant la fermeture (12h), sous le seuil de 15 min."""
        self._scan(8, 0)
        result = self._scan(11, 58)

        assert result['status'] == 'success'
        assert not AnomaliePointage.objects.filter(
            employe=self.employe, type=AnomaliePointage.TYPE_DEPART_ANTICIPE
        ).exists()

    def test_sortie_tardive_ne_cree_pas_anomalie(self):
        """Sortie après-midi à 18h (après la fermeture 17h30) : jamais 'anticipée'."""
        self._scan(8, 0)
        self._scan(12, 0)
        self._scan(13, 30)
        result = self._scan(18, 0)

        assert result['status'] == 'success'
        assert not AnomaliePointage.objects.filter(
            employe=self.employe, type=AnomaliePointage.TYPE_DEPART_ANTICIPE
        ).exists()

    def test_entree_ne_declenche_jamais_la_detection(self):
        """Une entrée (même très en avance dans sa fenêtre) n'est pas une sortie."""
        result = self._scan(8, 0)

        assert result['status'] == 'success'
        assert not AnomaliePointage.objects.filter(
            employe=self.employe, type=AnomaliePointage.TYPE_DEPART_ANTICIPE
        ).exists()

    def test_garde_de_nuit_jamais_concernee(self):
        """_process_garde() est un chemin séparé : jamais de détection dessus."""
        Pointage.objects.create(employe=self.employe, site=self.site, date_pointage=self.today, periode="nuit", type_journee="garde", statut="absent")
        fake_now = _aware(self.today, 22, 0)
        with patch('pointage.services.timezone.now', return_value=fake_now):
            result = process_scan(
                matricule=self.employe.matricule,
                qr_token=str(self.employe.qr_code_token),
                site_id=self.site.id,
                mode='garde',
            )
        assert result['status'] == 'success'

        # Fin de garde très rapide après le début — aucune notion de
        # "fermeture officielle" ne s'applique aux gardes.
        fake_now2 = _aware(self.today, 22, 5)
        with patch('pointage.services.timezone.now', return_value=fake_now2):
            result2 = process_scan(
                matricule=self.employe.matricule,
                qr_token=str(self.employe.qr_code_token),
                site_id=self.site.id,
                mode='garde',
            )
        assert result2['status'] == 'success'
        assert not AnomaliePointage.objects.filter(
            employe=self.employe, type=AnomaliePointage.TYPE_DEPART_ANTICIPE
        ).exists()
