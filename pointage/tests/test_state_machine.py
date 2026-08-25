# pointage/tests/test_state_machine.py
#
# TESTS UNITAIRES DE LA MACHINE À ÉTATS
# ======================================

from datetime import time

from pointage.domain import (
    DayState,
    ScanActionType,
    PeriodType,
    AnomalyCode,
)
from pointage.state_machine import DayStateMachine


class TestDayStateMachineFromEmpty:
    """Tests des décisions depuis état EMPTY."""
    
    def test_morning_entry_within_window(self, empty_day_context):
        """Premier scan le matin : entrée matin autorisée."""
        machine = DayStateMachine()
        decision = machine.decide(empty_day_context)
        
        assert decision.allowed is True
        assert decision.action == ScanActionType.MORNING_ENTRY
        assert decision.next_state == DayState.MORNING_STARTED
        assert decision.period == PeriodType.MORNING
        assert decision.anomaly_code is None
    
    def test_morning_entry_with_tolerance_before(self, empty_day_context, standard_site_schedule):
        """Premier scan avant 08:00 mais dans la tolérance : accepté."""
        # 07:50 est 10 min avant 08:00, tolérance = 15 min
        context = empty_day_context
        context.current_time = time(7, 50)
        
        machine = DayStateMachine()
        decision = machine.decide(context)
        
        assert decision.allowed is True
        assert decision.action == ScanActionType.MORNING_ENTRY
    
    def test_morning_entry_without_tolerance_before(self, empty_day_context):
        """Premier scan bien avant 08:00 : refusé."""
        # 07:00 est hors tolérance
        context = empty_day_context
        context.current_time = time(7, 0)
        
        machine = DayStateMachine()
        decision = machine.decide(context)
        
        assert decision.allowed is False
        assert decision.anomaly_code == AnomalyCode.OUTSIDE_HOURS
    
    def test_afternoon_entry_without_morning(self, empty_day_context):
        """Premier scan l'après-midi : entrée après-midi autorisée, matin absent."""
        context = empty_day_context
        context.current_time = time(14, 41)  # ← Bug de départ à 14h41
        
        machine = DayStateMachine()
        decision = machine.decide(context)
        
        assert decision.allowed is True
        assert decision.action == ScanActionType.AFTERNOON_ENTRY
        assert decision.next_state == DayState.AFTERNOON_STARTED
        assert decision.period == PeriodType.AFTERNOON
        assert decision.warning == "Le matin sera considéré comme absent."
        assert decision.details['morning_absent'] is True
    
    def test_during_break_first_scan(self, empty_day_context):
        """Premier scan pendant la pause : refusé."""
        context = empty_day_context
        context.current_time = time(12, 30)  # Entre 12:00 et 13:30
        
        machine = DayStateMachine()
        decision = machine.decide(context)
        
        assert decision.allowed is False
        assert decision.anomaly_code == AnomalyCode.DURING_BREAK
        assert "entre deux périodes" in decision.message
    
    def test_outside_all_hours(self, empty_day_context):
        """Premier scan trop tard : refusé."""
        context = empty_day_context
        context.current_time = time(22, 0)
        
        machine = DayStateMachine()
        decision = machine.decide(context)
        
        assert decision.allowed is False
        assert decision.anomaly_code == AnomalyCode.OUTSIDE_HOURS


class TestDayStateMachineFromMorningStarted:
    """Tests des décisions depuis MORNING_STARTED."""
    
    def test_morning_exit_within_window(self, morning_started_context):
        """Sortie matin pendant fenêtre matin : acceptée."""
        context = morning_started_context
        context.current_time = time(11, 0)
        
        machine = DayStateMachine()
        decision = machine.decide(context)
        
        assert decision.allowed is True
        assert decision.action == ScanActionType.MORNING_EXIT
        assert decision.next_state == DayState.MORNING_FINISHED
        assert decision.period == PeriodType.MORNING
    
    def test_morning_exit_after_tolerance(self, morning_started_context):
        """Sortie matin après 12:00 mais dans la tolérance : acceptée."""
        context = morning_started_context
        context.current_time = time(12, 10)  # 10 min après fermeture, tolérance 15 min
        
        machine = DayStateMachine()
        decision = machine.decide(context)
        
        assert decision.allowed is True
        assert decision.action == ScanActionType.MORNING_EXIT
    
    def test_afternoon_entry_without_morning_exit(self, morning_started_context):
        """Tentative entrée après-midi sans sortie matin : refusée."""
        context = morning_started_context
        context.current_time = time(14, 0)
        
        machine = DayStateMachine()
        decision = machine.decide(context)
        
        assert decision.allowed is False
        assert decision.anomaly_code == AnomalyCode.MISSING_MORNING_EXIT
        assert "Sortie du matin manquante" in decision.message
    
    def test_break_during_morning_started(self, morning_started_context):
        """Pendant la pause avec matin commencé : refusé."""
        context = morning_started_context
        context.current_time = time(12, 30)
        
        machine = DayStateMachine()
        decision = machine.decide(context)
        
        assert decision.allowed is False
        assert decision.anomaly_code == AnomalyCode.DURING_BREAK


class TestDayStateMachineFromMorningFinished:
    """Tests des décisions depuis MORNING_FINISHED."""
    
    def test_afternoon_entry_within_window(self, morning_finished_context):
        """Entrée après-midi pendant fenêtre : acceptée."""
        context = morning_finished_context
        context.current_time = time(14, 0)
        
        machine = DayStateMachine()
        decision = machine.decide(context)
        
        assert decision.allowed is True
        assert decision.action == ScanActionType.AFTERNOON_ENTRY
        assert decision.next_state == DayState.AFTERNOON_STARTED
        assert decision.period == PeriodType.AFTERNOON
    
    def test_afternoon_entry_with_tolerance(self, morning_finished_context):
        """Entrée après-midi avant 13:30 mais dans la tolérance : acceptée."""
        context = morning_finished_context
        context.current_time = time(13, 20)  # 10 min avant ouverture, tolérance 15 min
        
        machine = DayStateMachine()
        decision = machine.decide(context)
        
        assert decision.allowed is True
        assert decision.action == ScanActionType.AFTERNOON_ENTRY
    
    def test_during_break_after_morning(self, morning_finished_context):
        """Pendant la pause après matin : refusé."""
        context = morning_finished_context
        context.current_time = time(12, 30)
        
        machine = DayStateMachine()
        decision = machine.decide(context)
        
        assert decision.allowed is False
        assert decision.anomaly_code == AnomalyCode.DURING_BREAK
    
    def test_afternoon_entry_too_early(self, morning_finished_context):
        """Entrée après-midi trop tôt (hors tolérance) : refusée."""
        context = morning_finished_context
        context.current_time = time(13, 10)  # 20 min avant ouverture, tolérance 15 min
        
        machine = DayStateMachine()
        decision = machine.decide(context)
        
        assert decision.allowed is False
        # 13:10 est entre la fin du matin (12:00) et l'ouverture après-midi
        # (13:30) : c'est la pause déjeuner, pas un dépassement des horaires
        # globaux du site. Conforme à la règle métier "Pause -> Refuser le
        # scan" : is_during_break() est prioritaire sur le check de
        # tolérance d'ouverture après-midi.
        assert decision.anomaly_code == AnomalyCode.DURING_BREAK


class TestDayStateMachineFromAfternoonStarted:
    """Tests des décisions depuis AFTERNOON_STARTED."""
    
    def test_afternoon_exit_within_window(self, afternoon_started_context):
        """Sortie après-midi pendant fenêtre : acceptée."""
        context = afternoon_started_context
        context.current_time = time(16, 0)
        
        machine = DayStateMachine()
        decision = machine.decide(context)
        
        assert decision.allowed is True
        assert decision.action == ScanActionType.AFTERNOON_EXIT
        assert decision.next_state == DayState.DAY_FINISHED
        assert decision.period == PeriodType.AFTERNOON
    
    def test_afternoon_exit_with_tolerance(self, afternoon_started_context):
        """Sortie après-midi après 17:30 mais dans la tolérance : acceptée."""
        context = afternoon_started_context
        context.current_time = time(17, 40)  # 10 min après fermeture, tolérance 15 min
        
        machine = DayStateMachine()
        decision = machine.decide(context)
        
        assert decision.allowed is True
        assert decision.action == ScanActionType.AFTERNOON_EXIT
    
    def test_afternoon_exit_late_without_tolerance(self, afternoon_started_context):
        """Sortie très tardive (après tolérance) : acceptée (contexte médical)."""
        context = afternoon_started_context
        context.current_time = time(18, 30)  # Bien après fermeture
        
        machine = DayStateMachine()
        decision = machine.decide(context)
        
        assert decision.allowed is True
        assert decision.action == ScanActionType.AFTERNOON_EXIT
        assert decision.details['late_exit'] is True
        assert "tardive" in decision.message.lower()
    
    def test_afternoon_exit_midnight(self, afternoon_started_context):
        """Sortie à minuit (urgence) : acceptée."""
        context = afternoon_started_context
        context.current_time = time(23, 59)
        
        machine = DayStateMachine()
        decision = machine.decide(context)
        
        # Sortie tardive : toujours autorisée (règle métier), quelle que
        # soit l'heure. Le filtre global d'heures ne s'applique pas à la
        # sortie après-midi précisément pour ce genre de cas (garde
        # prolongée, urgence médicale...).
        assert decision.allowed is True
        assert decision.action == ScanActionType.AFTERNOON_EXIT
        assert decision.warning is not None


class TestDayStateMachineFromDayFinished:
    """Tests des décisions depuis DAY_FINISHED."""
    
    def test_no_scan_allowed_after_day_finished(self, day_finished_context):
        """Après journée complète : aucun scan autorisé."""
        machine = DayStateMachine()
        decision = machine.decide(day_finished_context)
        
        assert decision.allowed is False
        assert decision.anomaly_code == AnomalyCode.DAY_COMPLETE
        assert "complète" in decision.message.lower()


class TestDayStateMachineScenarios:
    """Tests des scénarios complets de journée."""
    
    def test_full_normal_day_scenario(self, standard_site_schedule):
        """Scénario complet : entrée matin → sortie matin → entrée après-midi → sortie après-midi."""
        from pointage.domain import DayContext
        
        machine = DayStateMachine()
        
        # 1. Entrée matin à 08:15
        ctx1 = DayContext(
            morning_entry=False, morning_exit=False,
            afternoon_entry=False, afternoon_exit=False,
            current_time=time(8, 15),
            schedule=standard_site_schedule,
            site_id=1, employee_id=1
        )
        dec1 = machine.decide(ctx1)
        assert dec1.allowed and dec1.action == ScanActionType.MORNING_ENTRY
        
        # 2. Sortie matin à 11:45
        ctx2 = DayContext(
            morning_entry=True, morning_exit=False,
            afternoon_entry=False, afternoon_exit=False,
            current_time=time(11, 45),
            schedule=standard_site_schedule,
            site_id=1, employee_id=1
        )
        dec2 = machine.decide(ctx2)
        assert dec2.allowed and dec2.action == ScanActionType.MORNING_EXIT
        
        # 3. Entrée après-midi à 14:00
        ctx3 = DayContext(
            morning_entry=True, morning_exit=True,
            afternoon_entry=False, afternoon_exit=False,
            current_time=time(14, 0),
            schedule=standard_site_schedule,
            site_id=1, employee_id=1
        )
        dec3 = machine.decide(ctx3)
        assert dec3.allowed and dec3.action == ScanActionType.AFTERNOON_ENTRY
        
        # 4. Sortie après-midi à 17:15
        ctx4 = DayContext(
            morning_entry=True, morning_exit=True,
            afternoon_entry=True, afternoon_exit=False,
            current_time=time(17, 15),
            schedule=standard_site_schedule,
            site_id=1, employee_id=1
        )
        dec4 = machine.decide(ctx4)
        assert dec4.allowed and dec4.action == ScanActionType.AFTERNOON_EXIT
    
    def test_first_scan_afternoon_scenario(self, standard_site_schedule):
        """Scénario bug initial : premier scan à 14h41 doit être entrée après-midi (pas matin)."""
        from pointage.domain import DayContext
        
        machine = DayStateMachine()
        
        # Premier scan à 14h41
        ctx = DayContext(
            morning_entry=False, morning_exit=False,
            afternoon_entry=False, afternoon_exit=False,
            current_time=time(14, 41),
            schedule=standard_site_schedule,
            site_id=1, employee_id=1
        )
        
        decision = machine.decide(ctx)
        
        # ✓ CORRIGÉ : entrée après-midi, pas entrée matin
        assert decision.allowed is True
        assert decision.action == ScanActionType.AFTERNOON_ENTRY
        assert decision.next_state == DayState.AFTERNOON_STARTED
        assert decision.period == PeriodType.AFTERNOON
        # L'avertissement d'absence matin est porté par le champ `warning`,
        # séparé de `message` par design (cf. ScanDecision) — c'est
        # `_apply_scan_decision()` côté services.py qui combine les deux
        # pour l'affichage final à l'utilisateur.
        assert decision.warning is not None
        assert "matin sera considéré comme absent" in decision.warning
    
    def test_skip_morning_skip_afternoon_scenario(self, standard_site_schedule):
        """Scénario : entrer matin, puis quitter sans revenir l'après-midi."""
        from pointage.domain import DayContext
        
        machine = DayStateMachine()
        
        # 1. Entrée matin
        ctx1 = DayContext(
            morning_entry=False, morning_exit=False,
            afternoon_entry=False, afternoon_exit=False,
            current_time=time(8, 0),
            schedule=standard_site_schedule,
            site_id=1, employee_id=1
        )
        dec1 = machine.decide(ctx1)
        assert dec1.allowed and dec1.action == ScanActionType.MORNING_ENTRY
        
        # 2. Sortie matin
        ctx2 = DayContext(
            morning_entry=True, morning_exit=False,
            afternoon_entry=False, afternoon_exit=False,
            current_time=time(12, 0),
            schedule=standard_site_schedule,
            site_id=1, employee_id=1
        )
        dec2 = machine.decide(ctx2)
        assert dec2.allowed and dec2.action == ScanActionType.MORNING_EXIT
        
        # 3. Fermeture journée (fin du jour, pas d'après-midi)
        # Note: Ceci sera géré par la couche application (clôture automatique)
        # La machine accepte simplement d'attendre
        ctx3 = DayContext(
            morning_entry=True, morning_exit=True,
            afternoon_entry=False, afternoon_exit=False,
            current_time=time(18, 0),  # Après heures
            schedule=standard_site_schedule,
            site_id=1, employee_id=1
        )
        # On ne peut pas scanner à 18:00 (hors heures)
        dec3 = machine.decide(ctx3)
        assert dec3.allowed is False


class TestDayStateMachineEdgeCases:
    """Tests des cas limites."""
    
    def test_break_exact_boundaries(self, standard_site_schedule):
        """Test des limites exactes de la pause."""
        from pointage.domain import DayContext
        
        machine = DayStateMachine()
        
        # Exactement à 12:00 : pas en pause
        ctx1 = DayContext(
            morning_entry=False, morning_exit=False,
            afternoon_entry=False, afternoon_exit=False,
            current_time=time(12, 0),
            schedule=standard_site_schedule,
            site_id=1, employee_id=1
        )
        dec1 = machine.decide(ctx1)
        # À 12:00, on peut faire une sortie matin
        
        # Exactement à 13:30 : pas en pause
        ctx2 = DayContext(
            morning_entry=True, morning_exit=True,
            afternoon_entry=False, afternoon_exit=False,
            current_time=time(13, 30),
            schedule=standard_site_schedule,
            site_id=1, employee_id=1
        )
        dec2 = machine.decide(ctx2)
        assert dec2.allowed is True
        assert dec2.action == ScanActionType.AFTERNOON_ENTRY
    
    def test_different_site_schedules(self, extended_site_schedule):
        """Test avec un horaire différent (centre étendu)."""
        from pointage.domain import DayContext
        
        machine = DayStateMachine()
        
        # 06:00 : ouverture du centre
        ctx = DayContext(
            morning_entry=False, morning_exit=False,
            afternoon_entry=False, afternoon_exit=False,
            current_time=time(6, 0),
            schedule=extended_site_schedule,
            site_id=1, employee_id=1
        )
        
        decision = machine.decide(ctx)
        assert decision.allowed is True
        assert decision.action == ScanActionType.MORNING_ENTRY
    
    def test_logging_output(self, morning_started_context, caplog):
        """Vérifier que les logs sont générés."""
        import logging
        caplog.set_level(logging.DEBUG)
        
        machine = DayStateMachine()
        machine.decide(morning_started_context)
        
        # Vérifier qu'il y a des logs
        assert any('[DayStateMachine' in record.message for record in caplog.records)
