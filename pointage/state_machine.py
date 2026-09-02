# pointage/state_machine.py
#
# MACHINE À ÉTATS PURE
# ====================
#
# Logique métier pour décider des transitions de pointage.
#
# Contraintes :
# - N'importe JAMAIS Django
# - N'accède JAMAIS à la base de données
# - Reçoit un DayContext (état actuel)
# - Retourne un ScanDecision (quoi faire)
# - Aucun effet secondaire

import logging
from datetime import datetime, date

from pointage.domain import (
    DayState,
    DayContext,
    ScanDecision,
    ScanActionType,
    PeriodType,
    AnomalyCode,
)

logger = logging.getLogger(__name__)


class DayStateMachine:
    """Machine à états pour le pointage normal d'une journée."""

    @staticmethod
    def _arrival_details(current_time, open_time):
        if current_time < open_time:
            minutes = int(
                (open_time.hour * 60 + open_time.minute)
                - (current_time.hour * 60 + current_time.minute)
            )
            return {
                'early_arrival': True,
                'early_arrival_minutes': minutes,
                'scheduled_open': open_time.isoformat(),
                'actual_arrival': current_time.isoformat(),
            }
        return {
            'early_arrival': False,
            'early_arrival_minutes': 0,
            'scheduled_open': open_time.isoformat(),
            'actual_arrival': current_time.isoformat(),
        }

    @staticmethod
    def _entry_allowed(window, current_time, tolerance):
        """Entrée: ouverture - tolérance jusqu'à la fermeture officielle.

        La tolérance post-fermeture ne doit pas transformer une entrée tardive
        en entrée de la période précédente.
        """
        current_dt = datetime.combine(date.today(), current_time)
        open_dt = datetime.combine(date.today(), window.open_time)
        close_dt = datetime.combine(date.today(), window.close_time)
        return open_dt - tolerance <= current_dt <= close_dt

    @staticmethod
    def _exit_allowed(window, current_time, tolerance):
        """Sortie: ouverture officielle jusqu'à fermeture + tolérance."""
        current_dt = datetime.combine(date.today(), current_time)
        open_dt = datetime.combine(date.today(), window.open_time)
        close_dt = datetime.combine(date.today(), window.close_time)
        return open_dt <= current_dt <= close_dt + tolerance

    def decide(self, context: DayContext) -> ScanDecision:
        current_state = context.get_current_state()
        logger.debug(
            f"[DayStateMachine] Deciding for {context} "
            f"(site={context.site_id}, emp={context.employee_id})"
        )

        # Les sorties après-midi tardives restent possibles afin de permettre
        # l'enregistrement des heures supplémentaires.
        if current_state not in (DayState.AFTERNOON_STARTED, DayState.DAY_FINISHED):
            if not context.schedule.is_within_global_hours(context.current_time):
                return ScanDecision(
                    allowed=False,
                    message=(
                        "Scan en dehors des heures autorisées "
                        f"({context.schedule.morning_window.open_time.strftime('%H:%M')}–"
                        f"{context.schedule.afternoon_window.close_time.strftime('%H:%M')})."
                    ),
                    anomaly_code=AnomalyCode.OUTSIDE_HOURS,
                    details={
                        'current_time': context.current_time.isoformat(),
                        'morning_open': context.schedule.morning_window.open_time.isoformat(),
                        'afternoon_close': context.schedule.afternoon_window.close_time.isoformat(),
                    }
                )

        if current_state == DayState.EMPTY:
            return self._decide_from_empty(context)
        if current_state == DayState.MORNING_STARTED:
            return self._decide_from_morning_started(context)
        if current_state == DayState.MORNING_FINISHED:
            return self._decide_from_morning_finished(context)
        if current_state == DayState.AFTERNOON_STARTED:
            return self._decide_from_afternoon_started(context)
        if current_state == DayState.DAY_FINISHED:
            return self._decide_from_day_finished(context)

        return ScanDecision(
            allowed=False,
            message="État inconnu de la journée.",
            anomaly_code=AnomalyCode.INVALID_STATE,
            details={'state': str(current_state)}
        )

    def _decide_from_empty(self, context: DayContext) -> ScanDecision:
        if context.schedule.is_during_break(context.current_time):
            return ScanDecision(
                allowed=False,
                message="Vous êtes actuellement entre deux périodes de travail.",
                anomaly_code=AnomalyCode.DURING_BREAK,
                details={'current_time': context.current_time.isoformat()}
            )

        if self._entry_allowed(
            context.schedule.morning_window,
            context.current_time,
            context.schedule.tolerance,
        ):
            return ScanDecision(
                allowed=True,
                message="Entrée matin enregistrée.",
                action=ScanActionType.MORNING_ENTRY,
                next_state=DayState.MORNING_STARTED,
                period=PeriodType.MORNING,
                details={
                    'window': 'morning',
                    **self._arrival_details(
                        context.current_time,
                        context.schedule.morning_window.open_time,
                    ),
                }
            )

        if self._entry_allowed(
            context.schedule.afternoon_window,
            context.current_time,
            context.schedule.tolerance,
        ):
            return ScanDecision(
                allowed=True,
                message="Entrée après-midi enregistrée.",
                action=ScanActionType.AFTERNOON_ENTRY,
                next_state=DayState.AFTERNOON_STARTED,
                period=PeriodType.AFTERNOON,
                warning="Le matin sera considéré comme absent.",
                details={
                    'window': 'afternoon',
                    'morning_absent': True,
                    **self._arrival_details(
                        context.current_time,
                        context.schedule.afternoon_window.open_time,
                    ),
                }
            )

        return ScanDecision(
            allowed=False,
            message="Heure invalide pour un premier scan.",
            anomaly_code=AnomalyCode.OUTSIDE_HOURS,
            details={'current_time': context.current_time.isoformat()}
        )

    def _decide_from_morning_started(self, context: DayContext) -> ScanDecision:
        if self._exit_allowed(
            context.schedule.morning_window,
            context.current_time,
            context.schedule.tolerance,
        ):
            return ScanDecision(
                allowed=True,
                message="Sortie matin enregistrée.",
                action=ScanActionType.MORNING_EXIT,
                next_state=DayState.MORNING_FINISHED,
                period=PeriodType.MORNING,
                details={'window': 'morning'}
            )

        if self._entry_allowed(
            context.schedule.afternoon_window,
            context.current_time,
            context.schedule.tolerance,
        ):
            return ScanDecision(
                allowed=False,
                message="Sortie du matin manquante. Veuillez contacter un administrateur.",
                anomaly_code=AnomalyCode.MISSING_MORNING_EXIT,
                details={'current_time': context.current_time.isoformat()}
            )

        if context.schedule.is_during_break(context.current_time):
            return ScanDecision(
                allowed=False,
                message="Vous êtes actuellement entre deux périodes de travail.",
                anomaly_code=AnomalyCode.DURING_BREAK,
                details={'current_time': context.current_time.isoformat()}
            )

        return ScanDecision(
            allowed=False,
            message="Heure invalide pour une sortie matin.",
            anomaly_code=AnomalyCode.OUTSIDE_HOURS,
            details={'current_time': context.current_time.isoformat()}
        )

    def _decide_from_morning_finished(self, context: DayContext) -> ScanDecision:
        if self._entry_allowed(
            context.schedule.afternoon_window,
            context.current_time,
            context.schedule.tolerance,
        ):
            return ScanDecision(
                allowed=True,
                message="Entrée après-midi enregistrée.",
                action=ScanActionType.AFTERNOON_ENTRY,
                next_state=DayState.AFTERNOON_STARTED,
                period=PeriodType.AFTERNOON,
                details={
                    'window': 'afternoon',
                    **self._arrival_details(
                        context.current_time,
                        context.schedule.afternoon_window.open_time,
                    ),
                }
            )

        if context.schedule.is_during_break(context.current_time):
            return ScanDecision(
                allowed=False,
                message="Vous êtes actuellement entre deux périodes de travail.",
                anomaly_code=AnomalyCode.DURING_BREAK,
                details={'current_time': context.current_time.isoformat()}
            )

        return ScanDecision(
            allowed=False,
            message="Heure invalide pour une entrée après-midi.",
            anomaly_code=AnomalyCode.OUTSIDE_HOURS,
            details={'current_time': context.current_time.isoformat()}
        )

    def _decide_from_afternoon_started(self, context: DayContext) -> ScanDecision:
        if self._exit_allowed(
            context.schedule.afternoon_window,
            context.current_time,
            context.schedule.tolerance,
        ):
            late_exit = context.current_time > context.schedule.afternoon_window.close_time
            return ScanDecision(
                allowed=True,
                message=(
                    "Sortie après-midi enregistrée (tardive)."
                    if late_exit else "Sortie après-midi enregistrée."
                ),
                action=ScanActionType.AFTERNOON_EXIT,
                next_state=DayState.DAY_FINISHED,
                period=PeriodType.AFTERNOON,
                warning=(
                    "Sortie enregistrée après les heures de fermeture."
                    if late_exit else None
                ),
                details={'window': 'afternoon', 'late_exit': late_exit}
            )

        # Au-delà de la tolérance, la sortie reste autorisée : elle est
        # précisément ce qui permet de comptabiliser les heures sup.
        if context.schedule.afternoon_window.is_after_close(context.current_time):
            return ScanDecision(
                allowed=True,
                message="Sortie après-midi enregistrée (tardive).",
                action=ScanActionType.AFTERNOON_EXIT,
                next_state=DayState.DAY_FINISHED,
                period=PeriodType.AFTERNOON,
                warning="Sortie enregistrée après les heures de fermeture.",
                details={'window': 'afternoon', 'late_exit': True}
            )

        return ScanDecision(
            allowed=False,
            message="Heure invalide pour une sortie après-midi.",
            anomaly_code=AnomalyCode.OUTSIDE_HOURS,
            details={'current_time': context.current_time.isoformat()}
        )

    def _decide_from_day_finished(self, context: DayContext) -> ScanDecision:
        return ScanDecision(
            allowed=False,
            message="Journée déjà complète (4/4 scans enregistrés).",
            anomaly_code=AnomalyCode.DAY_COMPLETE,
            details={'state': 'day_finished'}
        )
