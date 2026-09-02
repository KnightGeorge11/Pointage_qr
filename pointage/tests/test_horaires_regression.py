from datetime import time, timedelta

from django.test import TestCase

from pointage.context import build_site_schedule, DEFAULT_TOLERANCE_MINUTES
from pointage.domain import DayState, DayStateMachine
from pointage.models import Site


class HorairesMetierRegressionTests(TestCase):
    """Régressions sur les règles horaires centrales du projet."""

    def setUp(self):
        self.site = Site.objects.create(
            nom="Site horaires regression",
            adresse="Test",
            heure_ouverture_matin="08:00",
            heure_fermeture_matin="12:00",
            heure_ouverture_apres_midi="13:00",
            heure_fermeture_apres_midi="17:00",
            tolerance_minutes=None,
        )

    def test_tolerance_systeme_est_de_trente_minutes(self):
        schedule = build_site_schedule(self.site)
        self.assertEqual(schedule.tolerance, timedelta(minutes=30))
        self.assertEqual(DEFAULT_TOLERANCE_MINUTES, 30)

    def test_arrivee_0750_est_une_arrivee_anticipee_et_non_un_retard(self):
        schedule = build_site_schedule(self.site)
        context = __import__('pointage.domain', fromlist=['DayContext']).DayContext(
            morning_entry=False,
            morning_exit=False,
            afternoon_entry=False,
            afternoon_exit=False,
            current_time=time(7, 50),
            schedule=schedule,
            site_id=self.site.id,
            employee_id=1,
        )

        decision = DayStateMachine().decide(context)

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.next_state, DayState.MORNING_STARTED)
        self.assertEqual(decision.details['early_arrival'], True)
        self.assertEqual(decision.details['early_arrival_minutes'], 10)
        self.assertEqual(decision.details['actual_arrival'], '07:50:00')

    def test_heure_1300_est_le_debut_apres_midi(self):
        schedule = build_site_schedule(self.site)
        context = __import__('pointage.domain', fromlist=['DayContext']).DayContext(
            morning_entry=True,
            morning_exit=True,
            afternoon_entry=False,
            afternoon_exit=False,
            current_time=time(13, 0),
            schedule=schedule,
            site_id=self.site.id,
            employee_id=1,
        )

        decision = DayStateMachine().decide(context)

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.next_state, DayState.AFTERNOON_STARTED)
