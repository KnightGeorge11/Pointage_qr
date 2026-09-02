# pointage/context.py
#
# CONTEXT BUILDER - COUCHE D'ADAPTATION
# ======================================
#
# Lit les modèles Django et construit des objets métier purs (DayContext).
# Cette couche est la SEULE qui connaît Django et accède à la base.
# Elle crée un pont entre Django et la logique métier.

import logging
from datetime import time, timedelta, date
from typing import Optional, Tuple

from django.utils import timezone

from pointage.domain import (
    DayContext,
    SiteSchedule,
    TimeWindow,
)
from pointage.models import Pointage, Site

logger = logging.getLogger(__name__)


# Règle métier par défaut : 30 minutes de tolérance. Une arrivée avant
# l'ouverture officielle reste une arrivée anticipée et conserve son heure
# réelle (ex. 07:50 pour une ouverture à 08:00).
DEFAULT_TOLERANCE_MINUTES = 30
"""Tolérance par défaut en minutes. Peut être surchargée par site."""


def build_site_schedule(site: Site, tolerance_minutes: Optional[int] = None) -> SiteSchedule:
    """Construit un SiteSchedule à partir d'un modèle Site Django."""
    if tolerance_minutes is None:
        tolerance_minutes = site.tolerance_minutes
    if tolerance_minutes is None:
        tolerance_minutes = DEFAULT_TOLERANCE_MINUTES

    if tolerance_minutes < 0:
        raise ValueError("La tolérance ne peut pas être négative")

    if site.heure_fermeture_matin <= site.heure_ouverture_matin:
        logger.error(
            "[build_site_schedule] Site %s: fermeture matin <= ouverture matin",
            site.id,
        )
        raise ValueError(
            f"Site {site.nom}: heure de fermeture matin doit être après ouverture"
        )

    if site.heure_fermeture_apres_midi <= site.heure_ouverture_apres_midi:
        logger.error(
            "[build_site_schedule] Site %s: fermeture après-midi <= ouverture après-midi",
            site.id,
        )
        raise ValueError(
            f"Site {site.nom}: heure de fermeture après-midi doit être après ouverture"
        )

    morning_window = TimeWindow(
        open_time=site.heure_ouverture_matin,
        close_time=site.heure_fermeture_matin,
    )
    afternoon_window = TimeWindow(
        open_time=site.heure_ouverture_apres_midi,
        close_time=site.heure_fermeture_apres_midi,
    )

    tolerance = timedelta(minutes=tolerance_minutes)
    schedule = SiteSchedule(
        morning_window=morning_window,
        afternoon_window=afternoon_window,
        tolerance=tolerance,
    )

    logger.debug(
        "[build_site_schedule] Site %s (%s): %s",
        site.id,
        site.nom,
        schedule,
    )
    return schedule


def _get_morning_pointage(
    employee_id: int, date_target: date, lock: bool = False
) -> Optional[Pointage]:
    """Récupère le pointage matin, avec verrouillage optionnel."""
    queryset = Pointage.objects.select_for_update() if lock else Pointage.objects
    try:
        return queryset.get(
            employe_id=employee_id,
            date_pointage=date_target,
            periode='matin',
            type_journee='normal',
        )
    except Pointage.DoesNotExist:
        return None


def _get_afternoon_pointage(
    employee_id: int, date_target: date, lock: bool = False
) -> Optional[Pointage]:
    """Récupère le pointage après-midi, avec verrouillage optionnel."""
    queryset = Pointage.objects.select_for_update() if lock else Pointage.objects
    try:
        return queryset.get(
            employe_id=employee_id,
            date_pointage=date_target,
            periode='apres_midi',
            type_journee='normal',
        )
    except Pointage.DoesNotExist:
        return None


def collect_day_context(
    employee_id: int,
    site: Site,
    date_target: Optional[date] = None,
    current_time: Optional[time] = None,
    lock: bool = False,
) -> DayContext:
    """Construit un DayContext à partir de l'état réel en base."""
    if date_target is None:
        date_target = timezone.localtime(timezone.now()).date()

    logger.debug(
        "[collect_day_context] employee=%s, site=%s, date=%s",
        employee_id,
        site.id,
        date_target,
    )

    if current_time is None:
        current_time = timezone.localtime(timezone.now()).time()

    schedule = build_site_schedule(site, tolerance_minutes=site.tolerance_minutes)

    morning_pointage = _get_morning_pointage(employee_id, date_target, lock=lock)
    afternoon_pointage = _get_afternoon_pointage(employee_id, date_target, lock=lock)

    morning_entry = morning_pointage is not None and morning_pointage.heure_arrivee is not None
    morning_exit = morning_pointage is not None and morning_pointage.heure_depart is not None
    afternoon_entry = afternoon_pointage is not None and afternoon_pointage.heure_arrivee is not None
    afternoon_exit = afternoon_pointage is not None and afternoon_pointage.heure_depart is not None

    context = DayContext(
        morning_entry=morning_entry,
        morning_exit=morning_exit,
        afternoon_entry=afternoon_entry,
        afternoon_exit=afternoon_exit,
        current_time=current_time,
        schedule=schedule,
        site_id=site.id,
        employee_id=employee_id,
    )

    logger.debug("[collect_day_context] Result: %s", context)
    return context


def collect_day_context_for_scan(
    employee_id: int,
    site_id: int,
    date_target: Optional[date] = None,
    current_time: Optional[time] = None,
    lock: bool = False,
) -> Tuple[DayContext, Site]:
    """Récupère le site et construit le contexte métier correspondant."""
    logger.debug(
        "[collect_day_context_for_scan] employee=%s, site=%s",
        employee_id,
        site_id,
    )
    site = Site.objects.get(id=site_id)
    context = collect_day_context(
        employee_id=employee_id,
        site=site,
        date_target=date_target,
        current_time=current_time,
        lock=lock,
    )
    return context, site
