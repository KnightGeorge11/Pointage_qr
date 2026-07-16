# pointage/tests/conftest.py
#
# Configuration pytest et fixtures réutilisables
# ================================================

from datetime import time, timedelta
import pytest

from pointage.domain import (
    TimeWindow,
    SiteSchedule,
    DayContext,
)


# ─── FIXTURES POUR LES HORAIRES ──────────────────────────────────────────────

@pytest.fixture
def standard_site_schedule():
    """
    Horaire standard d'un site médical :
    - Matin : 08:00 - 12:00
    - Après-midi : 13:30 - 17:30
    - Tolérance : 15 minutes
    """
    morning = TimeWindow(time(8, 0), time(12, 0))
    afternoon = TimeWindow(time(13, 30), time(17, 30))
    tolerance = timedelta(minutes=15)
    return SiteSchedule(morning, afternoon, tolerance)


@pytest.fixture
def extended_site_schedule():
    """
    Horaire étendu (centre d'urgences 24h) :
    - Matin : 06:00 - 14:00
    - Après-midi : 14:00 - 22:00
    - Tolérance : 30 minutes
    """
    morning = TimeWindow(time(6, 0), time(14, 0))
    afternoon = TimeWindow(time(14, 0), time(22, 0))
    tolerance = timedelta(minutes=30)
    return SiteSchedule(morning, afternoon, tolerance)


@pytest.fixture
def evening_site_schedule():
    """
    Horaire décalé (consultation du soir) :
    - Matin : 14:00 - 17:00
    - Après-midi : 17:00 - 21:00
    - Tolérance : 10 minutes
    """
    morning = TimeWindow(time(14, 0), time(17, 0))
    afternoon = TimeWindow(time(17, 0), time(21, 0))
    tolerance = timedelta(minutes=10)
    return SiteSchedule(morning, afternoon, tolerance)


# ─── FIXTURES POUR LES CONTEXTES DE JOURNÉE ──────────────────────────────────

@pytest.fixture
def empty_day_context(standard_site_schedule):
    """Contexte d'une journée qui vient de commencer."""
    return DayContext(
        morning_entry=False,
        morning_exit=False,
        afternoon_entry=False,
        afternoon_exit=False,
        current_time=time(8, 0),
        schedule=standard_site_schedule,
        site_id=1,
        employee_id=1
    )


@pytest.fixture
def morning_started_context(standard_site_schedule):
    """Contexte d'une journée avec entrée matin enregistrée."""
    return DayContext(
        morning_entry=True,
        morning_exit=False,
        afternoon_entry=False,
        afternoon_exit=False,
        current_time=time(10, 0),
        schedule=standard_site_schedule,
        site_id=1,
        employee_id=1
    )


@pytest.fixture
def morning_finished_context(standard_site_schedule):
    """Contexte d'une journée avec entrée et sortie matin."""
    return DayContext(
        morning_entry=True,
        morning_exit=True,
        afternoon_entry=False,
        afternoon_exit=False,
        current_time=time(12, 0),
        schedule=standard_site_schedule,
        site_id=1,
        employee_id=1
    )


@pytest.fixture
def afternoon_started_context(standard_site_schedule):
    """Contexte d'une journée avec matin terminé et après-midi commencé."""
    return DayContext(
        morning_entry=True,
        morning_exit=True,
        afternoon_entry=True,
        afternoon_exit=False,
        current_time=time(14, 0),
        schedule=standard_site_schedule,
        site_id=1,
        employee_id=1
    )


@pytest.fixture
def day_finished_context(standard_site_schedule):
    """Contexte d'une journée complète."""
    return DayContext(
        morning_entry=True,
        morning_exit=True,
        afternoon_entry=True,
        afternoon_exit=True,
        current_time=time(17, 30),
        schedule=standard_site_schedule,
        site_id=1,
        employee_id=1
    )


@pytest.fixture
def morning_absent_context(standard_site_schedule):
    """Contexte d'une journée sans matin mais avec après-midi."""
    return DayContext(
        morning_entry=False,
        morning_exit=False,
        afternoon_entry=True,
        afternoon_exit=False,
        current_time=time(14, 0),
        schedule=standard_site_schedule,
        site_id=1,
        employee_id=1
    )


@pytest.fixture
def afternoon_absent_context(standard_site_schedule):
    """Contexte d'une journée avec matin mais sans après-midi."""
    return DayContext(
        morning_entry=True,
        morning_exit=True,
        afternoon_entry=False,
        afternoon_exit=True,  # Journée fermée sans après-midi
        current_time=time(17, 30),
        schedule=standard_site_schedule,
        site_id=1,
        employee_id=1
    )
