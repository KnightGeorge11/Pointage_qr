from datetime import time, timedelta

from django.test import TestCase

from pointage.context import build_site_schedule, DEFAULT_TOLERANCE_MINUTES
from pointage.domain import DayContext, DayState, AnomalyCode
from pointage.state_machine import DayStateMachine
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

    def _context(self, current_time, **state):
        return DayContext(
            morning_entry=state.get('morning_entry', False),
            morning_exit=state.get('morning_exit', False),
            afternoon_entry=state.get('afternoon_entry', False),
            afternoon_exit=state.get('afternoon_exit', False),
            current_time=current_time,
            schedule=build_site_schedule(self.site),
            site_id=self.site.id,
            employee_id=1,
        )

    def test_defaults_du_modele_site_sont_0800_1200_1300_1700(self):
        site = Site.objects.create(nom="Site defaults", adresse="Test")
        # Un TimeField fraîchement instancié peut conserver sa valeur de
        # défaut sous forme de chaîne. Après persistance, Django recharge la
        # valeur sous forme de datetime.time, qui est le contrat public du
        # modèle utilisé par le domaine.
        site.refresh_from_db()
        self.assertEqual(site.heure_ouverture_matin, time(8, 0))
        self.assertEqual(site.heure_fermeture_matin, time(12, 0))
        self.assertEqual(site.heure_ouverture_apres_midi, time(13, 0))
        self.assertEqual(site.heure_fermeture_apres_midi, time(17, 0))

    def test_tolerance_systeme_est_de_trente_minutes(self):
        schedule = build_site_schedule(self.site)
        self.assertEqual(schedule.tolerance, timedelta(minutes=30))
        self.assertEqual(DEFAULT_TOLERANCE_MINUTES, 30)

    def test_arrivee_0750_est_une_arrivee_anticipee_et_non_un_retard(self):
        decision = DayStateMachine().decide(self._context(time(7, 50)))

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.next_state, DayState.MORNING_STARTED)
        self.assertTrue(decision.details['early_arrival'])
        self.assertEqual(decision.details['early_arrival_minutes'], 10)
        self.assertEqual(decision.details['actual_arrival'], '07:50:00')

    def test_premier_scan_apres_fermeture_matin_ne_devient_pas_une_entree_matin(self):
        decision = DayStateMachine().decide(self._context(time(12, 15)))

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.anomaly_code, AnomalyCode.OUTSIDE_HOURS)

    def test_heure_1300_est_le_debut_apres_midi(self):
        decision = DayStateMachine().decide(self._context(
            time(13, 0), morning_entry=True, morning_exit=True
        ))

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.next_state, DayState.AFTERNOON_STARTED)

    def test_sortie_apres_midi_a_1715_est_acceptee_et_signalee_tardive(self):
        decision = DayStateMachine().decide(self._context(
            time(17, 15), morning_entry=True, morning_exit=True, afternoon_entry=True
        ))

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.next_state, DayState.DAY_FINISHED)
        self.assertTrue(decision.details['late_exit'])

    def test_sortie_apres_midi_apres_17h_est_acceptee_pour_heures_sup(self):
        decision = DayStateMachine().decide(self._context(
            time(18, 15), morning_entry=True, morning_exit=True, afternoon_entry=True
        ))

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.next_state, DayState.DAY_FINISHED)
        self.assertTrue(decision.details['late_exit'])

    def test_sortie_apres_midi_a_17h_est_normale_sans_heures_sup(self):
        decision = DayStateMachine().decide(self._context(
            time(17, 0), morning_entry=True, morning_exit=True, afternoon_entry=True
        ))

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.next_state, DayState.DAY_FINISHED)
        self.assertFalse(decision.details['late_exit'])
