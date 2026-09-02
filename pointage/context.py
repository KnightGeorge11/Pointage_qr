# pointage/context.py
#
# CONTEXT BUILDER - COUCHE D'ADAPTATION
# ======================================
#
# Lit les modèles Django et construit des objets métier purs (DayContext).
# Cette couche est la SEULE qui connaît Django et accède à la base.

import logging
from datetime import time, timedelta, date
from typing import Optional

from django.utils import timezone

from pointage.domain import DayContext, SiteSchedule, TimeWindow
from pointage.models import Pointage, Site

logger = logging.getLogger(__name__)


# Règle métier par défaut du projet : une arrivée peut être enregistrée
# jusqu'à 30 minutes avant l'ouverture officielle (ex. 07:50 pour 08:00).
# La valeur peut toujours être surchargée par site via Site.tolerance_minutes.
DEFAULT_TOLERANCE_MINUTES = 30


def build_site_schedule(site: Site, tolerance_minutes: Optional[int] = None) -> SiteSchedule:
    """Construit un SiteSchedule à partir d'un modèle Site Django."""
    if tolerance_minutes is None:
        tolerance_minutes = site.tolerance_minutes
    if tolerance_minutes is None:
        tolerance_minutes = DEFAULT_TOLERANCE_MINUTES

    if tolerance_minutes < 0:
        raise ValueError("La tolérance ne peut pas être négative")

    if site.heure_fermeture_matin <= site.heure_ouverture_matin:
        raise ValueError(
            f"Site {site.nom}: heure de fermeture matin doit être après ouverture"
        )

    if site.heure_fermeture_apres_midi <= site.heure_ouverture_apres_midi:
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

    schedule = SiteSchedule(
        morning_window=morning_window,
        afternoon_window=afternoon_window,
        tolerance=timedelta(minutes=tolerance_minutes),
    )

    logger.debug("[build_site_schedule] Site %s (%s): %s", site.id, site.nom, schedule)
    return schedule


def _get_morning_pointage(employee_id: int, date_target: date, lock: bool = False) -> Optional[Pointage]:
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


def _get_afternoon_pointage(employee_id: int, date_target: date, lock: bool = False) -> Optional[Pointage]:
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
    """Construit le contexte métier représentant l'état réel de la journée."""
    if date_target is None:
        date_target = timezone.localtime(timezone.now()).date()
    if current_time is None:
        current_time = timezone.localtime(timezone.now()).time()

    morning = _get_morning_pointage(employee_id, date_target, lock=lock)
    afternoon = _get_afternoon_pointage(employee_id, date_target, lock=lock)

    schedule = build_site_schedule(site)

    return DayContext(
        morning_entry=bool(morning and morning.heure_arrivee),
        morning_exit=bool(morning and morning.heure_depart),
        afternoon_entry=bool(afternoon and afternoon.heure_arrivee),
        afternoon_exit=bool(afternoon and afternoon.heure_depart),
        current_time=current_time,
        schedule=schedule,
        site_id=site.id,
        employee_id=employee_id,
    )
