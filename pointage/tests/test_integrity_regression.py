from datetime import date, time

from django.db import IntegrityError, transaction
from django.test import TestCase

from pointage.models import Employe, Pointage, Poste, Site


class PointageIntegrityRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.poste = Poste.objects.create(nom='INT-TEST')
        cls.site = Site.objects.create(
            nom='Site INT-TEST',
            adresse='Test',
            heure_ouverture_matin=time(8, 0),
            heure_fermeture_matin=time(12, 0),
            heure_ouverture_apres_midi=time(13, 0),
            heure_fermeture_apres_midi=time(17, 0),
        )
        cls.employe = Employe.objects.create(
            nom='Test', prenom='Integrity', matricule='INT-001', poste=cls.poste,
        )

    def test_normal_pointage_cannot_have_departure_before_arrival(self):
        pointage = Pointage(
            employe=self.employe,
            site=self.site,
            date_pointage=date(2026, 9, 2),
            periode='apres_midi',
            type_journee='normal',
            heure_arrivee=time(15, 0),
            heure_depart=time(14, 0),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                pointage.save()

    def test_garde_cannot_be_registered_on_day_period(self):
        pointage = Pointage(
            employe=self.employe,
            site=self.site,
            date_pointage=date(2026, 9, 2),
            periode='apres_midi',
            type_journee='garde',
            heure_arrivee=time(13, 0),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                pointage.save()

    def test_night_pointage_can_cross_midnight(self):
        pointage = Pointage.objects.create(
            employe=self.employe,
            site=self.site,
            date_pointage=date(2026, 9, 2),
            date_depart=date(2026, 9, 3),
            periode='nuit',
            type_journee='garde',
            heure_arrivee=time(20, 0),
            heure_depart=time(6, 0),
        )
        self.assertEqual(pointage.periode, 'nuit')
        self.assertEqual(pointage.type_journee, 'garde')
