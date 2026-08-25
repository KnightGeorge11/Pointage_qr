# pointage/tests/test_domain.py
#
# TESTS UNITAIRES DE LA COUCHE DOMAIN
# ====================================
#
# Tests des objets métier purs sans dépendances Django.

from datetime import time, timedelta
import pytest

from pointage.domain import (
    DayState,
    AnomalyCode,
    ScanActionType,
    PeriodType,
    TimeWindow,
    SiteSchedule,
    DayContext,
    ScanDecision,
    ScanAttempt,
)


# ─── TESTS TimeWindow ────────────────────────────────────────────────────────

class TestTimeWindow:
    """Tests de la classe TimeWindow."""
    
    def test_creation(self):
        """TimeWindow se crée correctement."""
        window = TimeWindow(
            open_time=time(8, 0),
            close_time=time(12, 0)
        )
        assert window.open_time == time(8, 0)
        assert window.close_time == time(12, 0)
    
    def test_contains_within_window(self):
        """contains() retourne True pour une heure dans la fenêtre."""
        window = TimeWindow(time(8, 0), time(12, 0))
        assert window.contains(time(8, 0)) is True
        assert window.contains(time(10, 0)) is True
        assert window.contains(time(12, 0)) is True
    
    def test_contains_outside_window(self):
        """contains() retourne False pour une heure hors fenêtre."""
        window = TimeWindow(time(8, 0), time(12, 0))
        assert window.contains(time(7, 59)) is False
        assert window.contains(time(12, 1)) is False
    
    def test_contains_with_tolerance_before(self):
        """contains() accepte les heures avant ouverture avec tolérance."""
        window = TimeWindow(time(8, 0), time(12, 0))
        tolerance = timedelta(minutes=15)
        # 07:50 est 10 min avant 08:00, donc OK avec tolérance 15 min
        assert window.contains(time(7, 50), tolerance=tolerance) is True
        # 07:45 est 15 min avant 08:00, donc OK avec tolérance 15 min
        assert window.contains(time(7, 45), tolerance=tolerance) is True
        # 07:44 est 16 min avant 08:00, donc NOK
        assert window.contains(time(7, 44), tolerance=tolerance) is False
    
    def test_contains_with_tolerance_after(self):
        """contains() accepte les heures après fermeture avec tolérance."""
        window = TimeWindow(time(8, 0), time(12, 0))
        tolerance = timedelta(minutes=15)
        # 12:10 est 10 min après 12:00, donc OK
        assert window.contains(time(12, 10), tolerance=tolerance) is True
        # 12:15 est 15 min après 12:00, donc OK
        assert window.contains(time(12, 15), tolerance=tolerance) is True
        # 12:16 est 16 min après 12:00, donc NOK
        assert window.contains(time(12, 16), tolerance=tolerance) is False
    
    def test_is_before_open(self):
        """is_before_open() détecte les heures avant ouverture."""
        window = TimeWindow(time(8, 0), time(12, 0))
        assert window.is_before_open(time(7, 59)) is True
        assert window.is_before_open(time(8, 0)) is False
        assert window.is_before_open(time(10, 0)) is False
    
    def test_is_after_close(self):
        """is_after_close() détecte les heures après fermeture."""
        window = TimeWindow(time(8, 0), time(12, 0))
        assert window.is_after_close(time(12, 1)) is True
        assert window.is_after_close(time(12, 0)) is False
        assert window.is_after_close(time(10, 0)) is False


# ─── TESTS SiteSchedule ──────────────────────────────────────────────────────

class TestSiteSchedule:
    """Tests de la classe SiteSchedule."""
    
    @pytest.fixture
    def schedule(self):
        """Crée un horaire de référence."""
        morning = TimeWindow(time(8, 0), time(12, 0))
        afternoon = TimeWindow(time(13, 30), time(17, 30))
        tolerance = timedelta(minutes=15)
        return SiteSchedule(morning, afternoon, tolerance)
    
    def test_creation(self, schedule):
        """SiteSchedule se crée correctement."""
        assert schedule.morning_window.open_time == time(8, 0)
        assert schedule.afternoon_window.open_time == time(13, 30)
        assert schedule.tolerance == timedelta(minutes=15)
    
    def test_is_during_break_before_break(self, schedule):
        """is_during_break() retourne False avant la pause."""
        assert schedule.is_during_break(time(11, 0)) is False
    
    def test_is_during_break_during_break(self, schedule):
        """is_during_break() retourne True pendant la pause."""
        # Entre 12:00 et 13:30
        assert schedule.is_during_break(time(12, 30)) is True
    
    def test_is_during_break_boundaries(self, schedule):
        """is_during_break() ne compte pas les heures limites."""
        # Exactement à 12:00 et 13:30, pas en pause
        assert schedule.is_during_break(time(12, 0)) is False
        assert schedule.is_during_break(time(13, 30)) is False
    
    def test_is_during_break_after_break(self, schedule):
        """is_during_break() retourne False après la pause."""
        assert schedule.is_during_break(time(14, 0)) is False
    
    def test_is_within_global_hours_valid(self, schedule):
        """is_within_global_hours() accepte les heures valides."""
        # 08:00 (ouverture matin)
        assert schedule.is_within_global_hours(time(8, 0)) is True
        # 17:30 (fermeture après-midi)
        assert schedule.is_within_global_hours(time(17, 30)) is True
        # Milieu de journée
        assert schedule.is_within_global_hours(time(12, 0)) is True
    
    def test_is_within_global_hours_with_tolerance_before(self, schedule):
        """is_within_global_hours() accepte avant 08:00 avec tolérance."""
        # 15 min avant 08:00 = 07:45, OK
        assert schedule.is_within_global_hours(time(7, 45)) is True
        # 20 min avant 08:00 = 07:40, NOK
        assert schedule.is_within_global_hours(time(7, 40)) is False
    
    def test_is_within_global_hours_with_tolerance_after(self, schedule):
        """is_within_global_hours() accepte après 17:30 avec tolérance."""
        # 15 min après 17:30 = 17:45, OK
        assert schedule.is_within_global_hours(time(17, 45)) is True
        # 20 min après 17:30 = 17:50, NOK
        assert schedule.is_within_global_hours(time(17, 50)) is False
    
    def test_is_within_global_hours_outside(self, schedule):
        """is_within_global_hours() rejette les heures trop en dehors."""
        # 22:00 est trop tard
        assert schedule.is_within_global_hours(time(22, 0)) is False
        # 05:00 est trop tôt
        assert schedule.is_within_global_hours(time(5, 0)) is False


# ─── TESTS DayContext ────────────────────────────────────────────────────────

class TestDayContext:
    """Tests de la classe DayContext."""
    
    @pytest.fixture
    def schedule(self):
        """Horaire de référence."""
        morning = TimeWindow(time(8, 0), time(12, 0))
        afternoon = TimeWindow(time(13, 30), time(17, 30))
        return SiteSchedule(morning, afternoon, timedelta(minutes=15))
    
    @pytest.fixture
    def empty_context(self, schedule):
        """Contexte vide (journée qui commence)."""
        return DayContext(
            morning_entry=False,
            morning_exit=False,
            afternoon_entry=False,
            afternoon_exit=False,
            current_time=time(8, 0),
            schedule=schedule,
            site_id=1,
            employee_id=1
        )
    
    def test_creation(self, empty_context):
        """DayContext se crée correctement."""
        assert empty_context.morning_entry is False
        assert empty_context.morning_exit is False
        assert empty_context.site_id == 1
    
    def test_get_current_state_empty(self, empty_context):
        """get_current_state() retourne EMPTY."""
        assert empty_context.get_current_state() == DayState.EMPTY
    
    def test_get_current_state_morning_started(self, schedule):
        """get_current_state() retourne MORNING_STARTED."""
        context = DayContext(
            morning_entry=True,
            morning_exit=False,
            afternoon_entry=False,
            afternoon_exit=False,
            current_time=time(8, 30),
            schedule=schedule,
            site_id=1,
            employee_id=1
        )
        assert context.get_current_state() == DayState.MORNING_STARTED
    
    def test_get_current_state_morning_finished(self, schedule):
        """get_current_state() retourne MORNING_FINISHED."""
        context = DayContext(
            morning_entry=True,
            morning_exit=True,
            afternoon_entry=False,
            afternoon_exit=False,
            current_time=time(12, 0),
            schedule=schedule,
            site_id=1,
            employee_id=1
        )
        assert context.get_current_state() == DayState.MORNING_FINISHED
    
    def test_get_current_state_afternoon_started(self, schedule):
        """get_current_state() retourne AFTERNOON_STARTED."""
        context = DayContext(
            morning_entry=True,
            morning_exit=True,
            afternoon_entry=True,
            afternoon_exit=False,
            current_time=time(14, 0),
            schedule=schedule,
            site_id=1,
            employee_id=1
        )
        assert context.get_current_state() == DayState.AFTERNOON_STARTED
    
    def test_get_current_state_day_finished(self, schedule):
        """get_current_state() retourne DAY_FINISHED."""
        context = DayContext(
            morning_entry=True,
            morning_exit=True,
            afternoon_entry=True,
            afternoon_exit=True,
            current_time=time(17, 30),
            schedule=schedule,
            site_id=1,
            employee_id=1
        )
        assert context.get_current_state() == DayState.DAY_FINISHED
    
    def test_is_morning_absent_no_morning_but_afternoon(self, schedule):
        """is_morning_absent() = True si pas de matin mais entrée après-midi."""
        context = DayContext(
            morning_entry=False,
            morning_exit=False,
            afternoon_entry=True,  # ← Entrée après-midi
            afternoon_exit=False,
            current_time=time(14, 0),
            schedule=schedule,
            site_id=1,
            employee_id=1
        )
        assert context.is_morning_absent() is True
    
    def test_is_morning_absent_morning_exists(self, schedule):
        """is_morning_absent() = False si entrée matin enregistrée."""
        context = DayContext(
            morning_entry=True,  # ← Entrée matin
            morning_exit=False,
            afternoon_entry=True,
            afternoon_exit=False,
            current_time=time(14, 0),
            schedule=schedule,
            site_id=1,
            employee_id=1
        )
        assert context.is_morning_absent() is False
    
    def test_is_morning_absent_empty_day(self, schedule):
        """is_morning_absent() = False pour journée vide."""
        context = DayContext(
            morning_entry=False,
            morning_exit=False,
            afternoon_entry=False,
            afternoon_exit=False,
            current_time=time(8, 0),
            schedule=schedule,
            site_id=1,
            employee_id=1
        )
        assert context.is_morning_absent() is False
    
    def test_is_afternoon_absent_complete_day_no_afternoon(self, schedule):
        """is_afternoon_absent() = True si journée terminée mais pas d'après-midi."""
        context = DayContext(
            morning_entry=True,
            morning_exit=True,
            afternoon_entry=False,  # ← Pas d'après-midi
            afternoon_exit=True,   # ← Journée terminée
            current_time=time(17, 30),
            schedule=schedule,
            site_id=1,
            employee_id=1
        )
        assert context.is_afternoon_absent() is True
    
    def test_is_afternoon_absent_afternoon_exists(self, schedule):
        """is_afternoon_absent() = False si entrée après-midi enregistrée."""
        context = DayContext(
            morning_entry=True,
            morning_exit=True,
            afternoon_entry=True,  # ← Entrée après-midi
            afternoon_exit=True,
            current_time=time(17, 30),
            schedule=schedule,
            site_id=1,
            employee_id=1
        )
        assert context.is_afternoon_absent() is False
    
    def test_is_afternoon_absent_only_morning(self, schedule):
        """is_afternoon_absent() = False si seulement matin enregistré."""
        context = DayContext(
            morning_entry=True,
            morning_exit=True,
            afternoon_entry=False,
            afternoon_exit=False,  # ← Journée pas fermée
            current_time=time(14, 0),
            schedule=schedule,
            site_id=1,
            employee_id=1
        )
        assert context.is_afternoon_absent() is False


# ─── TESTS ScanDecision ──────────────────────────────────────────────────────

class TestScanDecision:
    """Tests de la classe ScanDecision."""
    
    def test_allowed_decision(self):
        """ScanDecision allowed se crée correctement."""
        decision = ScanDecision(
            allowed=True,
            message="Entrée matin enregistrée",
            action=ScanActionType.MORNING_ENTRY,
            next_state=DayState.MORNING_STARTED,
            period=PeriodType.MORNING
        )
        assert decision.allowed is True
        assert decision.action == ScanActionType.MORNING_ENTRY
        assert decision.anomaly_code is None
    
    def test_denied_decision(self):
        """ScanDecision denied se crée correctement."""
        decision = ScanDecision(
            allowed=False,
            message="Scan pendant la pause",
            anomaly_code=AnomalyCode.DURING_BREAK
        )
        assert decision.allowed is False
        assert decision.anomaly_code == AnomalyCode.DURING_BREAK
        assert decision.action is None
    
    def test_to_dict_allowed(self):
        """to_dict() sérialise correctement une décision acceptée."""
        decision = ScanDecision(
            allowed=True,
            message="OK",
            action=ScanActionType.MORNING_ENTRY,
            next_state=DayState.MORNING_STARTED,
            period=PeriodType.MORNING
        )
        d = decision.to_dict()
        assert d['allowed'] is True
        assert d['action'] == 'entree_matin'
        assert d['next_state'] == 'morning_started'
        assert d['period'] == 'matin'
    
    def test_to_dict_denied(self):
        """to_dict() sérialise correctement une décision refusée."""
        decision = ScanDecision(
            allowed=False,
            message="Pause",
            anomaly_code=AnomalyCode.DURING_BREAK
        )
        d = decision.to_dict()
        assert d['allowed'] is False
        assert d['anomaly_code'] == 'during_break'
        assert d['action'] is None
    
    def test_with_warning(self):
        """ScanDecision peut inclure un avertissement."""
        decision = ScanDecision(
            allowed=True,
            message="Scan accepté",
            action=ScanActionType.MORNING_EXIT,
            warning="Sortie tardive détectée"
        )
        assert decision.warning == "Sortie tardive détectée"
    
    def test_with_details(self):
        """ScanDecision peut contenir des détails."""
        decision = ScanDecision(
            allowed=True,
            message="OK",
            action=ScanActionType.MORNING_ENTRY,
            details={'delay_minutes': 5}
        )
        assert decision.details['delay_minutes'] == 5


# ─── TESTS ScanAttempt ────────────────────────────────────────────────────────

class TestScanAttempt:
    """Tests de la classe ScanAttempt."""
    
    def test_creation(self):
        """ScanAttempt se crée correctement."""
        attempt = ScanAttempt(
            employee_id=1,
            site_id=1,
            current_time=time(8, 30)
        )
        assert attempt.employee_id == 1
        assert attempt.site_id == 1
        assert attempt.current_time == time(8, 30)
    
    def test_to_dict(self):
        """to_dict() sérialise correctement."""
        attempt = ScanAttempt(
            employee_id=123,
            site_id=5,
            current_time=time(14, 41)
        )
        d = attempt.to_dict()
        assert d['employee_id'] == 123
        assert d['site_id'] == 5
        assert d['current_time'] == '14:41:00'


# ─── TESTS Enums ─────────────────────────────────────────────────────────────

class TestEnums:
    """Tests des énumérations."""
    
    def test_day_state_values(self):
        """DayState contient tous les états attendus."""
        assert DayState.EMPTY.value == "empty"
        assert DayState.MORNING_STARTED.value == "morning_started"
        assert DayState.MORNING_FINISHED.value == "morning_finished"
        assert DayState.AFTERNOON_STARTED.value == "afternoon_started"
        assert DayState.DAY_FINISHED.value == "day_finished"
    
    def test_anomaly_code_values(self):
        """AnomalyCode contient les codes attendus."""
        assert AnomalyCode.INVALID_QR.value == "invalid_qr"
        assert AnomalyCode.DURING_BREAK.value == "during_break"
        assert AnomalyCode.MISSING_MORNING_EXIT.value == "missing_morning_exit"
    
    def test_scan_action_type_values(self):
        """ScanActionType contient les actions attendues."""
        assert ScanActionType.MORNING_ENTRY.value == "entree_matin"
        assert ScanActionType.MORNING_EXIT.value == "sortie_matin"
        assert ScanActionType.AFTERNOON_ENTRY.value == "entree_apres_midi"
        assert ScanActionType.AFTERNOON_EXIT.value == "sortie_apres_midi"
    
    def test_period_type_values(self):
        """PeriodType contient les périodes attendues."""
        assert PeriodType.MORNING.value == "matin"
        assert PeriodType.AFTERNOON.value == "apres_midi"
        assert PeriodType.NIGHT.value == "nuit"
