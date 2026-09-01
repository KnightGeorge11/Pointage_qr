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
    """Machine à états pour le pointage normal d'une journée.

    Détermine si un scan est autorisé et quelle action effectuer,
    basé UNIQUEMENT sur :
    - L'état courant (scans enregistrés)
    - L'heure actuelle
    - Les horaires du site

    Une arrivée avant l'heure officielle reste une arrivée anticipée :
    la tolérance sert uniquement à autoriser le scan et ne doit jamais
    remplacer l'heure réelle du scan par l'heure théorique d'ouverture.
    """

    @staticmethod
    def _arrival_details(current_time, open_time):
        """Retourne les métadonnées d'une arrivée anticipée, sans modifier
        l'heure réelle enregistrée.
        """
        if current_time < open_time:
            minutes = int((
                (open_time.hour * 60 + open_time.minute)
                - (current_time.hour * 60 + current_time.minute)
            ))
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

    def decide(self, context: DayContext) -> ScanDecision:
        """Décide si un scan est autorisé et quelle action effectuer."""
        logger.debug(
            f"[DayStateMachine] Deciding for {context} "
            f"(site={context.site_id}, emp={context.employee_id})"
        )

        current_state = context.get_current_state()
        logger.debug(f"[DayStateMachine] Current state: {current_state.value}")

        # Les sorties après-midi tardives doivent rester possibles pour
        # permettre l'enregistrement des heures supplémentaires.
        if current_state not in (DayState.AFTERNOON_STARTED, DayState.DAY_FINISHED):
            if not context.schedule.is_within_global_hours(context.current_time):
                logger.info(
                    f"[DayStateMachine] Outside global hours: {context.current_time}"
                )
                return ScanDecision(
                    allowed=False,
                    message=f"Scan en dehors des heures autorisées "
                            f"({context.schedule.morning_window.open_time.strftime('%H:%M')}–"
                            f"{context.schedule.afternoon_window.close_time.strftime('%H:%M')}).",
                    anomaly_code=AnomalyCode.OUTSIDE_HOURS,
                    details={
                        'current_time': context.current_time.isoformat(),
                        'morning_open': context.schedule.morning_window.open_time.isoformat(),
                        'afternoon_close': context.schedule.afternoon_window.close_time.isoformat(),
                    }
                )

        if current_state == DayState.EMPTY:
            return self._decide_from_empty(context)
        elif current_state == DayState.MORNING_STARTED:
            return self._decide_from_morning_started(context)
        elif current_state == DayState.MORNING_FINISHED:
            return self._decide_from_morning_finished(context)
        elif current_state == DayState.AFTERNOON_STARTED:
            return self._decide_from_afternoon_started(context)
        elif current_state == DayState.DAY_FINISHED:
            return self._decide_from_day_finished(context)
        else:
            logger.error(f"[DayStateMachine] Unknown state: {current_state}")
            return ScanDecision(
                allowed=False,
                message="État inconnu de la journée.",
                anomaly_code=AnomalyCode.INVALID_STATE,
                details={'state': str(current_state)}
            )

    def _decide_from_empty(self, context: DayContext) -> ScanDecision:
        """De EMPTY, déterminer l'action."""
        logger.debug("[DayStateMachine._decide_from_empty]")

        if context.schedule.is_during_break(context.current_time):
            logger.info("[DayStateMachine] During break")
            return ScanDecision(
                allowed=False,
                message="Vous êtes actuellement entre deux périodes de travail.",
                anomaly_code=AnomalyCode.DURING_BREAK,
                details={'current_time': context.current_time.isoformat()}
            )

        if context.schedule.morning_window.contains(
            context.current_time,
            tolerance=context.schedule.tolerance
        ):
            logger.info("[DayStateMachine] Allowing morning entry")
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

        if context.schedule.afternoon_window.contains(
            context.current_time,
            tolerance=context.schedule.tolerance
        ):
            logger.info("[DayStateMachine] Allowing afternoon entry (morning will be absent)")
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

        logger.warning("[DayStateMachine] Invalid time for first scan")
        return ScanDecision(
            allowed=False,
            message="Heure invalide pour un premier scan.",
            anomaly_code=AnomalyCode.OUTSIDE_HOURS,
            details={'current_time': context.current_time.isoformat()}
        )

    def _decide_from_morning_started(self, context: DayContext) -> ScanDecision:
        """De MORNING_STARTED, seule action possible : sortie matin."""
        logger.debug("[DayStateMachine._decide_from_morning_started]")

        if context.schedule.morning_window.contains(
            context.current_time,
            tolerance=context.schedule.tolerance
        ):
            logger.info("[DayStateMachine] Allowing morning exit")
            return ScanDecision(
                allowed=True,
                message="Sortie matin enregistrée.",
                action=ScanActionType.MORNING_EXIT,
                next_state=DayState.MORNING_FINISHED,
                period=PeriodType.MORNING,
                details={'window': 'morning'}
            )

        if context.schedule.afternoon_window.contains(
            context.current_time,
            tolerance=context.schedule.tolerance
        ):
            logger.warning("[DayStateMachine] Afternoon entry without morning exit")
            return ScanDecision(
                allowed=False,
                message="Sortie du matin manquante. Veuillez contacter un administrateur.",
                anomaly_code=AnomalyCode.MISSING_MORNING_EXIT,
                details={'current_time': context.current_time.isoformat()}
            )

        if context.schedule.is_during_break(context.current_time):
            logger.info("[DayStateMachine] During break")
            return ScanDecision(
                allowed=False,
                message="Vous êtes actuellement entre deux périodes de travail.",
                anomaly_code=AnomalyCode.DURING_BREAK,
                details={'current_time': context.current_time.isoformat()}
            )

        logger.warning("[DayStateMachine] Invalid time for morning exit")
        return ScanDecision(
            allowed=False,
            message="Heure invalide pour une sortie matin.",
            anomaly_code=AnomalyCode.OUTSIDE_HOURS,
            details={'current_time': context.current_time.isoformat()}
        )

    def _decide_from_morning_finished(self, context: DayContext) -> ScanDecision:
        """De MORNING_FINISHED, seule action possible : entrée après-midi."""
        logger.debug("[DayStateMachine._decide_from_morning_finished]")

        if context.schedule.afternoon_window.contains(
            context.current_time,
            tolerance=context.schedule.tolerance
        ):
            logger.info("[DayStateMachine] Allowing afternoon entry")
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
            logger.info("[DayStateMachine] During break, waiting for afternoon")
            return ScanDecision(
                allowed=False,
                message="Vous êtes actuellement entre deux périodes de travail.",
                anomaly_code=AnomalyCode.DURING_BREAK,
                details={'current_time': context.current_time.isoformat()}
            )

        logger.warning("[DayStateMachine] Invalid time for afternoon entry")
        return ScanDecision(
            allowed=False,
            message="Heure invalide pour une entrée après-midi.",
            anomaly_code=AnomalyCode.OUTSIDE_HOURS,
            details={'current_time': context.current_time.isoformat()}
        )

    def _decide_from_afternoon_started(self, context: DayContext) -> ScanDecision:
        """De AFTERNOON_STARTED, seule action possible : sortie après-midi."""
        logger.debug("[DayStateMachine._decide_from_afternoon_started]")

        if context.schedule.afternoon_window.contains(
            context.current_time,
            tolerance=context.schedule.tolerance
        ):
            logger.info("[DayStateMachine] Allowing afternoon exit (within window)")
            return ScanDecision(
                allowed=True,
                message="Sortie après-midi enregistrée.",
                action=ScanActionType.AFTERNOON_EXIT,
                next_state=DayState.DAY_FINISHED,
                period=PeriodType.AFTERNOON,
                details={'window': 'afternoon'}
            )

        if context.schedule.afternoon_window.is_after_close(context.current_time):
            logger.info("[DayStateMachine] Allowing late afternoon exit")
            return ScanDecision(
                allowed=True,
                message="Sortie après-midi enregistrée (tardive).",
                action=ScanActionType.AFTERNOON_EXIT,
                next_state=DayState.DAY_FINISHED,
                period=PeriodType.AFTERNOON,
                warning="Sortie enregistrée après les heures de fermeture.",
                details={'window': 'afternoon', 'late_exit': True}
            )

        logger.warning("[DayStateMachine] Invalid time for afternoon exit")
        return ScanDecision(
            allowed=False,
            message="Heure invalide pour une sortie après-midi.",
            anomaly_code=AnomalyCode.OUTSIDE_HOURS,
            details={'current_time': context.current_time.isoformat()}
        )

    def _decide_from_day_finished(self, context: DayContext) -> ScanDecision:
        """De DAY_FINISHED, aucune action n'est possible."""
        logger.info("[DayStateMachine] Day already finished")
        return ScanDecision(
            allowed=False,
            message="Journée déjà complète (4/4 scans enregistrés).",
            anomaly_code=AnomalyCode.DAY_COMPLETE,
            details={'state': 'day_finished'}
        )
