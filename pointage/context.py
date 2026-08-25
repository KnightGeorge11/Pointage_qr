# pointage/context.py
#
# CONTEXT BUILDER - COUCHE D'ADAPTATION
# ======================================
#
# Lit les modèles Django et construit des objets métier purs (DayContext).
#
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


# ─── CONSTANTES ──────────────────────────────────────────────────────────────

DEFAULT_TOLERANCE_MINUTES = 15
"""Tolérance par défaut en minutes. Peut être surchargée per-site."""


# ─── BUILDER FUNCTIONS ────────────────────────────────────────────────────────

def build_site_schedule(site: Site, tolerance_minutes: Optional[int] = None) -> SiteSchedule:
    """
    Construit un SiteSchedule à partir d'un modèle Site Django.
    
    Paramètres
    ----------
    site : Site
        Modèle Site Django avec horaires
    
    tolerance_minutes : int, optional
        Tolérance en minutes. Si None, utilise DEFAULT_TOLERANCE_MINUTES.
    
    Retour
    ------
    SiteSchedule
        Objet métier avec horaires et tolérance
    
    Lève
    ----
    ValueError
        Si les horaires du site sont invalides
    """
    if tolerance_minutes is None:
        tolerance_minutes = DEFAULT_TOLERANCE_MINUTES
    
    # Vérifier cohérence des horaires
    if site.heure_fermeture_matin <= site.heure_ouverture_matin:
        logger.error(
            f"[build_site_schedule] Site {site.id}: "
            f"morning_close {site.heure_fermeture_matin} <= morning_open {site.heure_ouverture_matin}"
        )
        raise ValueError(
            f"Site {site.nom}: heure de fermeture matin doit être après ouverture"
        )
    
    if site.heure_fermeture_apres_midi <= site.heure_ouverture_apres_midi:
        logger.error(
            f"[build_site_schedule] Site {site.id}: "
            f"afternoon_close {site.heure_fermeture_apres_midi} <= afternoon_open {site.heure_ouverture_apres_midi}"
        )
        raise ValueError(
            f"Site {site.nom}: heure de fermeture après-midi doit être après ouverture"
        )
    
    morning_window = TimeWindow(
        open_time=site.heure_ouverture_matin,
        close_time=site.heure_fermeture_matin
    )
    
    afternoon_window = TimeWindow(
        open_time=site.heure_ouverture_apres_midi,
        close_time=site.heure_fermeture_apres_midi
    )
    
    tolerance = timedelta(minutes=tolerance_minutes)
    
    schedule = SiteSchedule(
        morning_window=morning_window,
        afternoon_window=afternoon_window,
        tolerance=tolerance
    )
    
    logger.debug(
        f"[build_site_schedule] Site {site.id} ({site.nom}): {schedule}"
    )
    
    return schedule


def _get_morning_pointage(
    employee_id: int, date_target: date, lock: bool = False
) -> Optional[Pointage]:
    """
    Récupère le pointage matin pour un employé et une date.
    
    Paramètres
    ----------
    employee_id : int
        ID de l'employé
    
    date_target : date
        Date cible
    
    lock : bool, optional
        Si True, verrouille la ligne (SELECT ... FOR UPDATE) pour la durée
        de la transaction englobante. À utiliser uniquement avant une prise
        de décision qui sera suivie d'une écriture, pour éviter qu'un scan
        concurrent du même employé ne lise un état obsolète.
    
    Retour
    ------
    Pointage or None
        Le pointage matin, ou None s'il n'existe pas
    """
    queryset = Pointage.objects.select_for_update() if lock else Pointage.objects
    try:
        return queryset.get(
            employe_id=employee_id,
            date_pointage=date_target,
            periode='matin',
            type_journee='normal'
        )
    except Pointage.DoesNotExist:
        return None


def _get_afternoon_pointage(
    employee_id: int, date_target: date, lock: bool = False
) -> Optional[Pointage]:
    """
    Récupère le pointage après-midi pour un employé et une date.
    
    Paramètres
    ----------
    employee_id : int
        ID de l'employé
    
    date_target : date
        Date cible
    
    lock : bool, optional
        Si True, verrouille la ligne (SELECT ... FOR UPDATE). Voir
        `_get_morning_pointage` pour le contexte d'utilisation.
    
    Retour
    ------
    Pointage or None
        Le pointage après-midi, ou None s'il n'existe pas
    """
    queryset = Pointage.objects.select_for_update() if lock else Pointage.objects
    try:
        return queryset.get(
            employe_id=employee_id,
            date_pointage=date_target,
            periode='apres_midi',
            type_journee='normal'
        )
    except Pointage.DoesNotExist:
        return None


def collect_day_context(
    employee_id: int,
    site: Site,
    date_target: Optional[date] = None,
    current_time: Optional[time] = None,
    lock: bool = False
) -> DayContext:
    """
    Construits un DayContext en lisant la base de données.
    
    Collecte :
    - Les pointages existants (matin/après-midi) pour l'employé
    - L'heure actuelle
    - Les horaires du site
    
    Retour
    ------
    DayContext
        Contexte métier purement représentatif de l'état courant
    
    Paramètres
    ----------
    employee_id : int
        ID de l'employé
    
    site : Site
        Site Django avec horaires
    
    date_target : date, optional
        Date à analyser. Par défaut, aujourd'hui (heure locale)
    
    current_time : time, optional
        Heure courante. Par défaut, maintenant (heure locale)
    
    lock : bool, optional
        Si True, verrouille (SELECT ... FOR UPDATE) les pointages du jour
        pour cet employé le temps de la transaction englobante. À activer
        quand ce contexte servira de base à une décision suivie d'une
        écriture (cf. `services._process_normal`), pour empêcher deux scans
        concurrents du même employé de produire une décision incohérente.
        Doit être appelé à l'intérieur d'un `transaction.atomic()`.
    
    Lève
    ----
    ValueError
        Si les paramètres sont invalides (ex: horaires incohérents)
    """
    # 1. Déterminer la date cible
    if date_target is None:
        date_target = timezone.localtime(timezone.now()).date()
    
    logger.debug(f"[collect_day_context] employee={employee_id}, site={site.id}, date={date_target}")
    
    # 2. Déterminer l'heure courante
    if current_time is None:
        current_time = timezone.localtime(timezone.now()).time()
    
    # 3. Construire le schedule du site
    schedule = build_site_schedule(site)
    
    # 4. Récupérer les pointages existants
    morning_pointage = _get_morning_pointage(employee_id, date_target, lock=lock)
    afternoon_pointage = _get_afternoon_pointage(employee_id, date_target, lock=lock)
    
    # 5. Extraire les flags (scans enregistrés)
    morning_entry = morning_pointage is not None and morning_pointage.heure_arrivee is not None
    morning_exit = morning_pointage is not None and morning_pointage.heure_depart is not None
    
    afternoon_entry = afternoon_pointage is not None and afternoon_pointage.heure_arrivee is not None
    afternoon_exit = afternoon_pointage is not None and afternoon_pointage.heure_depart is not None
    
    logger.debug(
        f"[collect_day_context] entries: M={morning_entry}, A={afternoon_entry} | "
        f"exits: M={morning_exit}, A={afternoon_exit}"
    )
    
    # 6. Construire le DayContext
    context = DayContext(
        morning_entry=morning_entry,
        morning_exit=morning_exit,
        afternoon_entry=afternoon_entry,
        afternoon_exit=afternoon_exit,
        current_time=current_time,
        schedule=schedule,
        site_id=site.id,
        employee_id=employee_id
    )
    
    logger.debug(f"[collect_day_context] Result: {context}")
    
    return context


def collect_day_context_for_scan(
    employee_id: int,
    site_id: int,
    date_target: Optional[date] = None,
    current_time: Optional[time] = None,
    lock: bool = False
) -> Tuple[DayContext, Site]:
    """
    Variante qui récupère aussi le Site et retourne un tuple.
    
    Utile pour process_scan() qui a besoin du Site.
    
    Paramètres
    ----------
    employee_id : int
        ID de l'employé
    
    site_id : int
        ID du site
    
    date_target : date, optional
        Date cible (par défaut aujourd'hui)
    
    current_time : time, optional
        Heure courante (par défaut maintenant)
    
    Retour
    ------
    Tuple[DayContext, Site]
        Le contexte et le site
    
    Lève
    ----
    Site.DoesNotExist
        Si le site n'existe pas
    
    ValueError
        Si les horaires du site sont invalides
    """
    logger.debug(f"[collect_day_context_for_scan] employee={employee_id}, site={site_id}")
    
    # Récupérer le site
    site = Site.objects.get(id=site_id)
    
    # Construire le contexte
    context = collect_day_context(
        employee_id=employee_id,
        site=site,
        date_target=date_target,
        current_time=current_time,
        lock=lock
    )
    
    return context, site
