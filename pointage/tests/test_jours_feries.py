from datetime import date

from django.test import TestCase

from pointage.models import JourFerie


class TestJourFerie(TestCase):
    def test_jour_ferie_est_ferie_seulement_sil_est_actif(self):
        JourFerie.objects.create(
            date=date(2026, 12, 25),
            nom="Noël",
            actif=True,
        )

        self.assertTrue(JourFerie.est_ferie(date(2026, 12, 25)))
        self.assertFalse(JourFerie.est_ferie(date(2026, 12, 26)))

    def test_jour_ferie_desactive_nest_pas_considere_ferie(self):
        JourFerie.objects.create(
            date=date(2026, 12, 25),
            nom="Noël",
            actif=False,
        )

        self.assertFalse(JourFerie.est_ferie(date(2026, 12, 25)))
