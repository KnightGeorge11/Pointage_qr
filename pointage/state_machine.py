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
from typing import Optional

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
    
    Décisions
    ---------
    - Premier scan matin → MORNING_STARTED
    - Premier scan après-midi → AFTERNOON_STARTED + matin marqué absent
    - Sortie matin → MORNING_FINISHED
    - Sortie après-midi → DAY_FINISHED
    - Transitions impossibles → Refusées
    
    Les absences ne sont JAMAIS créées comme états.
    Elles sont calculées lors des rapports RH.
    """
    
    def decide(self, context: DayContext) -> ScanDecision:
        """
        Décide si un scan est autorisé et quelle action effectuer.
        
        Paramètres
        ----------
        context : DayContext
            État courant de la journée (scans enregistrés, heure, horaires)
        
        Retour
        ------
        ScanDecision
            Décision (autorisé/refusé, action, prochaine état, anomalies)
        
        Notes
        -----
        Cette méthode est pure : aucun effet secondaire.
        """
        logger.debug(
            f"[DayStateMachine] Deciding for {context} "
            f"(site={context.site_id}, emp={context.employee_id})"
        )
        
        # 1. Détecter l'état courant
        current_state = context.get_current_state()
        logger.debug(f"[DayStateMachine] Current state: {current_state.value}")
        
        # 2. Vérifier les heures globales
        #
        # Ce filtre ne s'applique PAS à AFTERNOON_STARTED ni à DAY_FINISHED :
        # - AFTERNOON_STARTED : seule action possible = sortie après-midi.
        #   Une sortie tardive (heures supplémentaires, urgence médicale...)
        #   doit TOUJOURS être autorisée (règle métier). C'est
        #   _decide_from_afternoon_started() qui gère explicitement ce cas
        #   ("sortie tardive") ; le bloquer ici avant même d'y arriver
        #   contredirait cette règle.
        # - DAY_FINISHED : refuse de toute façon systématiquement tout scan,
        #   peu importe l'heure.
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
        
        # 3. Décider selon l'état
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
            # État inconnu (ne devrait jamais arriver ici)
            logger.error(f"[DayStateMachine] Unknown state: {current_state}")
            return ScanDecision(
                allowed=False,
                message="État inconnu de la journée.",
                anomaly_code=AnomalyCode.INVALID_STATE,
                details={'state': str(current_state)}
            )
    
    def _decide_from_empty(self, context: DayContext) -> ScanDecision:
        """De EMPTY, déterminer l'action.
        
        Possible :
        1. Entrée matin (si pendant fenêtre matin)
        2. Entrée après-midi (si pendant fenêtre après-midi, matin = absent)
        3. Pause → Refuser
        4. Hors heures → Refuser
        """
        logger.debug("[DayStateMachine._decide_from_empty]")
        
        # Vérifier pause
        if context.schedule.is_during_break(context.current_time):
            logger.info("[DayStateMachine] During break")
            return ScanDecision(
                allowed=False,
                message="Vous êtes actuellement entre deux périodes de travail.",
                anomaly_code=AnomalyCode.DURING_BREAK,
                details={'current_time': context.current_time.isoformat()}
            )
        
        # Matin ?
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
                details={'window': 'morning'}
            )
        
        # Après-midi ?
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
                details={'window': 'afternoon', 'morning_absent': True}
            )
        
        # Ni matin, ni après-midi, ni pause
        logger.warning("[DayStateMachine] Invalid time for first scan")
        return ScanDecision(
            allowed=False,
            message="Heure invalide pour un premier scan.",
            anomaly_code=AnomalyCode.OUTSIDE_HOURS,
            details={'current_time': context.current_time.isoformat()}
        )
    
    def _decide_from_morning_started(self, context: DayContext) -> ScanDecision:
        """De MORNING_STARTED, seule action possible : sortie matin.
        
        - Si pendant fenêtre matin → Sortie matin
        - Si pendant fenêtre après-midi → Refuser (sortie matin manquante)
        - Sinon → Refuser
        """
        logger.debug("[DayStateMachine._decide_from_morning_started]")
        
        # Sortie matin pendant fenêtre matin ?
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
        
        # Tentative de passer à l'après-midi sans sortie matin
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
        
        # Pendant la pause
        if context.schedule.is_during_break(context.current_time):
            logger.info("[DayStateMachine] During break")
            return ScanDecision(
                allowed=False,
                message="Vous êtes actuellement entre deux périodes de travail.",
                anomaly_code=AnomalyCode.DURING_BREAK,
                details={'current_time': context.current_time.isoformat()}
            )
        
        # Hors horaires
        logger.warning("[DayStateMachine] Invalid time for morning exit")
        return ScanDecision(
            allowed=False,
            message="Heure invalide pour une sortie matin.",
            anomaly_code=AnomalyCode.OUTSIDE_HOURS,
            details={'current_time': context.current_time.isoformat()}
        )
    
    def _decide_from_morning_finished(self, context: DayContext) -> ScanDecision:
        """De MORNING_FINISHED, seule action possible : entrée après-midi.
        
        - Si pendant fenêtre après-midi → Entrée après-midi
        - Si pendant pause → Refuser
        - Sinon → Refuser
        """
        logger.debug("[DayStateMachine._decide_from_morning_finished]")
        
        # Entrée après-midi pendant fenêtre après-midi ?
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
                details={'window': 'afternoon'}
            )
        
        # Pendant la pause
        if context.schedule.is_during_break(context.current_time):
            logger.info("[DayStateMachine] During break, waiting for afternoon")
            return ScanDecision(
                allowed=False,
                message="Vous êtes actuellement entre deux périodes de travail.",
                anomaly_code=AnomalyCode.DURING_BREAK,
                details={'current_time': context.current_time.isoformat()}
            )
        
        # Hors horaires
        logger.warning("[DayStateMachine] Invalid time for afternoon entry")
        return ScanDecision(
            allowed=False,
            message="Heure invalide pour une entrée après-midi.",
            anomaly_code=AnomalyCode.OUTSIDE_HOURS,
            details={'current_time': context.current_time.isoformat()}
        )
    
    def _decide_from_afternoon_started(self, context: DayContext) -> ScanDecision:
        """De AFTERNOON_STARTED, seule action possible : sortie après-midi.
        
        - Si pendant fenêtre après-midi → Sortie après-midi
        - Si après fermeture (sortie tardive) → Sortie après-midi autorisée
        - Sinon → Refuser
        """
        logger.debug("[DayStateMachine._decide_from_afternoon_started]")
        
        # Sortie après-midi dans la fenêtre ou après (sortie tardive autorisée)
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
        
        # Sortie tardive (après 17:30 par exemple)
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
        
        # Hors horaires
        logger.warning("[DayStateMachine] Invalid time for afternoon exit")
        return ScanDecision(
            allowed=False,
            message="Heure invalide pour une sortie après-midi.",
            anomaly_code=AnomalyCode.OUTSIDE_HOURS,
            details={'current_time': context.current_time.isoformat()}
        )
    
    def _decide_from_day_finished(self, context: DayContext) -> ScanDecision:
        """De DAY_FINISHED, aucune action n'est possible.
        
        La journée est terminée.
        """
        logger.info("[DayStateMachine] Day already finished")
        return ScanDecision(
            allowed=False,
            message="Journée déjà complète (4/4 scans enregistrés).",
            anomaly_code=AnomalyCode.DAY_COMPLETE,
            details={'state': 'day_finished'}
        )
