# pointage/tests/test_heures_supplementaires.py
#
# Vérifie Pointage.get_heures_supplementaires() : les heures sup
# commencent APRÈS l'heure de fermeture après-midi officielle du site,
# jamais un total journalier générique moins un seuil fixe (ancien calcul,
# faux — voir historique de conversation : un site à 7h/jour ou à 9h/jour
# donnait un résultat incorrect dans les deux sens avec un seuil de 8h).

from datetime import time, date, timedelta

from django.test import TestCase

from pointage.models import Employe, Site, Pointage


class HeuresSupplementairesTestCase(TestCase):

    def setUp(self):
        self.employe = Employe.objects.create(nom="T", prenom="U", matricule="HS001")

    def test_site_7h_par_jour_sortie_en_retard(self):
        """Site à 7h/jour (8h-12h, 13h-16h) : ancien calcul (total-8h) aurait
        donné 0, alors qu'il y a bien 1h après la fermeture réelle (16h)."""
        site = Site.objects.create(
            nom="Site7h", adresse="A",
            heure_ouverture_matin=time(8, 0), heure_fermeture_matin=time(12, 0),
            heure_ouverture_apres_midi=time(13, 0), heure_fermeture_apres_midi=time(16, 0),
        )
        p = Pointage.objects.create(
            employe=self.employe, site=site, date_pointage=date.today(),
            periode='apres_midi', type_journee='normal',
            heure_arrivee=time(13, 0), heure_depart=time(17, 0),
        )
        assert p.get_heures_supplementaires() == timedelta(hours=1)

    def test_site_9h_par_jour_sortie_pile_a_l_heure(self):
        """Site à 9h/jour (8h-12h, 13h-18h) : ancien calcul (total-8h) aurait
        donné 1h d'heures sup alors qu'il n'y en a aucune (sortie pile à
        l'heure officielle de fermeture, 18h)."""
        site = Site.objects.create(
            nom="Site9h", adresse="B",
            heure_ouverture_matin=time(8, 0), heure_fermeture_matin=time(12, 0),
            heure_ouverture_apres_midi=time(13, 0), heure_fermeture_apres_midi=time(18, 0),
        )
        p = Pointage.objects.create(
            employe=self.employe, site=site, date_pointage=date.today(),
            periode='apres_midi', type_journee='normal',
            heure_arrivee=time(13, 0), heure_depart=time(18, 0),
        )
        assert p.get_heures_supplementaires() == timedelta(0)

    def test_sortie_avant_fermeture_jamais_negatif(self):
        site = Site.objects.create(
            nom="Site", adresse="C",
            heure_ouverture_matin=time(8, 0), heure_fermeture_matin=time(12, 0),
            heure_ouverture_apres_midi=time(13, 0), heure_fermeture_apres_midi=time(18, 0),
        )
        p = Pointage.objects.create(
            employe=self.employe, site=site, date_pointage=date.today(),
            periode='apres_midi', type_journee='normal',
            heure_arrivee=time(13, 0), heure_depart=time(17, 30),
        )
        assert p.get_heures_supplementaires() == timedelta(0)

    def test_pointage_matin_jamais_concerne(self):
        site = Site.objects.create(
            nom="Site", adresse="D",
            heure_ouverture_matin=time(8, 0), heure_fermeture_matin=time(12, 0),
            heure_ouverture_apres_midi=time(13, 0), heure_fermeture_apres_midi=time(17, 0),
        )
        p = Pointage.objects.create(
            employe=self.employe, site=site, date_pointage=date.today(),
            periode='matin', type_journee='normal',
            heure_arrivee=time(8, 0), heure_depart=time(12, 0),
        )
        assert p.get_heures_supplementaires() == timedelta(0)

    def test_pointage_non_cloture_jamais_de_sup(self):
        """heure_depart absente (pas encore sorti) : pas de calcul possible."""
        site = Site.objects.create(
            nom="Site", adresse="E",
            heure_ouverture_matin=time(8, 0), heure_fermeture_matin=time(12, 0),
            heure_ouverture_apres_midi=time(13, 0), heure_fermeture_apres_midi=time(17, 0),
        )
        p = Pointage.objects.create(
            employe=self.employe, site=site, date_pointage=date.today(),
            periode='apres_midi', type_journee='normal',
            heure_arrivee=time(13, 0),
        )
        assert p.get_heures_supplementaires() == timedelta(0)

    def test_garde_de_nuit_jamais_concernee(self):
        site = Site.objects.create(
            nom="Site", adresse="F",
            heure_ouverture_matin=time(8, 0), heure_fermeture_matin=time(12, 0),
            heure_ouverture_apres_midi=time(13, 0), heure_fermeture_apres_midi=time(17, 0),
        )
        p = Pointage.objects.create(
            employe=self.employe, site=site, date_pointage=date.today(),
            periode='nuit', type_journee='garde',
            heure_arrivee=time(22, 0), heure_depart=time(6, 0),
        )
        assert p.get_heures_supplementaires() == timedelta(0)
