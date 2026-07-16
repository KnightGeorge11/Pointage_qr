# pointage/domain.py
#
# OBJETS MÉTIER PURS (Domain Objects)
# ====================================
#
# Cette couche contient les objets métier qui :
# - Représentent les concepts du domaine (scan, journée, contexte)
# - N'importent JAMAIS Django
# - N'accèdent JAMAIS à la base de données
# - Peuvent être utilisés indépendamment du framework
#
# Ces objets sont les "messages" échangés entre les couches.

from dataclasses import dataclass, field
from datetime import time, timedelta, datetime, date
from typing import Optional
from enum import Enum


# ─── ÉNUMÉRATIONS ───────────────────────────────────────────────────────────

class DayState(Enum):
    """États réels d'une journée de pointage normal.
    
    Représentent uniquement ce qui s'est RÉELLEMENT produit,
    jamais une absence ou une hypothèse.
    """
    EMPTY = "empty"                           # Aucun scan enregistré
    MORNING_STARTED = "morning_started"       # Entrée matin enregistrée
    MORNING_FINISHED = "morning_finished"     # Sortie matin enregistrée
    AFTERNOON_STARTED = "afternoon_started"   # Entrée après-midi enregistrée
    DAY_FINISHED = "day_finished"             # Sortie après-midi enregistrée


class AnomalyCode(Enum):
    """Codes d'anomalies détectées."""
    # Sécurité
    INVALID_QR = "invalid_qr"
    DUPLICATE_SCAN = "duplicate_scan"
    
    # Horaire
    OUTSIDE_HOURS = "outside_hours"
    DURING_BREAK = "during_break"
    
    # Transition
    DAY_COMPLETE = "day_complete"
    MISSING_MORNING_EXIT = "missing_morning_exit"
    TRANSITION_IMPOSSIBLE = "transition_impossible"
    
    # État
    INVALID_STATE = "invalid_state"


class ScanActionType(Enum):
    """Types d'actions de scan possibles."""
    MORNING_ENTRY = "entree_matin"
    MORNING_EXIT = "sortie_matin"
    AFTERNOON_ENTRY = "entree_apres_midi"
    AFTERNOON_EXIT = "sortie_apres_midi"
    GUARD_START = "debut_garde"
    GUARD_END = "fin_garde"


class PeriodType(Enum):
    """Périodes de travail."""
    MORNING = "matin"
    AFTERNOON = "apres_midi"
    NIGHT = "nuit"


# ─── OBJETS MÉTIER ──────────────────────────────────────────────────────────

@dataclass
class TimeWindow:
    """Fenêtre horaire d'une période.
    
    Représente l'intervalle horaire d'une période (ex: 08:00-12:00).
    Gère les calculs d'inclusion avec tolérance.
    """
    open_time: time
    close_time: time
    
    def contains(self, current_time: time, tolerance: timedelta = None) -> bool:
        """Vérifie si l'heure est dans cette fenêtre.
        
        Paramètres
        ----------
        current_time : time
            L'heure à tester
        tolerance : timedelta, optional
            Marge de tolérance (avant ouverture et après fermeture)
        
        Retour
        ------
        bool : True si l'heure est dans la fenêtre (±tolérance)
        """
        if tolerance is None:
            tolerance = timedelta(0)
        
        today = date.today()
        now_dt = datetime.combine(today, current_time)
        open_dt = datetime.combine(today, self.open_time)
        close_dt = datetime.combine(today, self.close_time)
        
        return open_dt - tolerance <= now_dt <= close_dt + tolerance
    
    def is_before_open(self, current_time: time) -> bool:
        """L'heure est avant l'ouverture?"""
        return current_time < self.open_time
    
    def is_after_close(self, current_time: time) -> bool:
        """L'heure est après la fermeture?"""
        return current_time > self.close_time
    
    def __repr__(self) -> str:
        return f"TimeWindow({self.open_time.strftime('%H:%M')}-{self.close_time.strftime('%H:%M')})"


@dataclass
class SiteSchedule:
    """Horaires d'un site pour une journée.
    
    Contient :
    - Les fenêtres horaires pour matin et après-midi
    - La tolérance applicable
    
    Gère les calculs relatifs aux horaires (pause, heures globales, etc).
    """
    morning_window: TimeWindow
    afternoon_window: TimeWindow
    tolerance: timedelta
    
    def is_during_break(self, current_time: time) -> bool:
        """Vérifie si on est en pause entre les deux périodes.
        
        La pause est définie comme l'intervalle entre :
        - La fermeture du matin
        - L'ouverture de l'après-midi
        
        Paramètres
        ----------
        current_time : time
        
        Retour
        ------
        bool : True si on est en pause (sans limites de tolérance)
        """
        today = date.today()
        now_dt = datetime.combine(today, current_time)
        close_morning_dt = datetime.combine(today, self.morning_window.close_time)
        open_afternoon_dt = datetime.combine(today, self.afternoon_window.open_time)
        
        return close_morning_dt < now_dt < open_afternoon_dt
    
    def is_within_global_hours(self, current_time: time) -> bool:
        """Vérifie si on est entre l'ouverture matin et fermeture après-midi.
        
        Inclut la tolérance avant et après.
        
        Paramètres
        ----------
        current_time : time
        
        Retour
        ------
        bool : True si l'heure est acceptée globalement
        """
        today = date.today()
        now_dt = datetime.combine(today, current_time)
        open_dt = datetime.combine(today, self.morning_window.open_time) - self.tolerance
        close_dt = datetime.combine(today, self.afternoon_window.close_time) + self.tolerance
        
        return open_dt <= now_dt <= close_dt
    
    def __repr__(self) -> str:
        return (f"SiteSchedule("
                f"matin={self.morning_window}, "
                f"apres-midi={self.afternoon_window}, "
                f"tolerance={self.tolerance})")


@dataclass
class DayContext:
    """Contexte métier d'une journée.
    
    Représente l'état actuel de la journée en enregistrant uniquement
    ce qui s'est RÉELLEMENT produit (les scans enregistrés).
    
    N'INTERPRÈTE JAMAIS les absences comme des états.
    Les absences sont calculées par les méthodes is_morning_absent(), etc.
    
    Attributs
    ---------
    morning_entry : bool
        True = scan d'entrée matin enregistré en base
        False = aucun scan d'entrée matin en base
    
    morning_exit : bool
        True = scan de sortie matin enregistré en base
        False = aucun scan de sortie matin en base
    
    afternoon_entry : bool
        True = scan d'entrée après-midi enregistré en base
        False = aucun scan d'entrée après-midi en base
    
    afternoon_exit : bool
        True = scan de sortie après-midi enregistré en base
        False = aucun scan de sortie après-midi en base
    
    current_time : time
        Heure courante du scan (heure locale)
    
    schedule : SiteSchedule
        Horaires et tolérance du site
    
    site_id : int
        Identifiant du site (pour logs/debug)
    
    employee_id : int
        Identifiant de l'employé (pour logs/debug)
    """
    morning_entry: bool
    morning_exit: bool
    afternoon_entry: bool
    afternoon_exit: bool
    current_time: time
    schedule: SiteSchedule
    site_id: int
    employee_id: int
    
    def get_current_state(self) -> DayState:
        """Détecte l'état courant basé sur les scans réels enregistrés.
        
        Retour
        ------
        DayState : État détecté
        """
        # Journée complète
        if self.afternoon_exit:
            return DayState.DAY_FINISHED
        
        # Après-midi commencé
        if self.afternoon_entry:
            return DayState.AFTERNOON_STARTED
        
        # Matin complet (sortie enregistrée)
        if self.morning_exit:
            return DayState.MORNING_FINISHED
        
        # Matin commencé (entrée enregistrée)
        if self.morning_entry:
            return DayState.MORNING_STARTED
        
        # Rien
        return DayState.EMPTY
    
    def is_morning_absent(self) -> bool:
        """Calcule si le matin est considéré comme absent.
        
        Le matin est absent si :
        - L'après-midi a commencé (au moins une entrée après-midi)
        - ET aucune trace du matin (pas d'entrée matin)
        
        Retour
        ------
        bool : True si le matin doit être considéré comme absent
        """
        return self.afternoon_entry and not self.morning_entry
    
    def is_afternoon_absent(self) -> bool:
        """Calcule si l'après-midi est considéré comme absent.
        
        L'après-midi est absent si :
        - La journée est terminée (sortie après-midi enregistrée)
        - ET aucune trace de l'après-midi (pas d'entrée après-midi)
        - ET le matin a au moins commencé (sinon c'est juste une absence globale)
        
        Retour
        ------
        bool : True si l'après-midi doit être considéré comme absent
        """
        return self.afternoon_exit and not self.afternoon_entry and self.morning_entry
    
    def __repr__(self) -> str:
        state = self.get_current_state()
        return (f"DayContext("
                f"state={state.value}, "
                f"entries=M:{self.morning_entry}/A:{self.afternoon_entry}, "
                f"exits=M:{self.morning_exit}/A:{self.afternoon_exit}, "
                f"time={self.current_time.strftime('%H:%M')}, "
                f"site={self.site_id})")


@dataclass
class ScanDecision:
    """Décision de la machine à états suite à une demande de scan.
    
    Indique si le scan est autorisé et quelle est l'action à effectuer.
    N'effectue JAMAIS aucune modification en base (pure décision).
    
    Attributs
    ---------
    allowed : bool
        Le scan est-il autorisé?
    
    message : str
        Message utilisateur (court et clair pour affichage)
    
    action : ScanActionType, optional
        L'action à effectuer si allowed=True
        Ex: MORNING_ENTRY, MORNING_EXIT, etc.
    
    next_state : DayState, optional
        L'état après cette action
    
    period : PeriodType, optional
        Période concernée (MORNING, AFTERNOON, NIGHT)
    
    anomaly_code : AnomalyCode, optional
        Code d'anomalie si allowed=False
    
    warning : str, optional
        Avertissement (scan accepté mais attention requise)
    
    details : dict
        Détails supplémentaires pour logs/debug
    """
    allowed: bool
    message: str
    action: Optional[ScanActionType] = None
    next_state: Optional[DayState] = None
    period: Optional[PeriodType] = None
    anomaly_code: Optional[AnomalyCode] = None
    warning: Optional[str] = None
    details: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convertir en dictionnaire pour réponse API/logs.
        
        Retour
        ------
        dict : Représentation sérialisable
        """
        return {
            'allowed': self.allowed,
            'message': self.message,
            'action': self.action.value if self.action else None,
            'next_state': self.next_state.value if self.next_state else None,
            'period': self.period.value if self.period else None,
            'anomaly_code': self.anomaly_code.value if self.anomaly_code else None,
            'warning': self.warning,
            'details': self.details,
        }
    
    def __repr__(self) -> str:
        status = "✓ ALLOWED" if self.allowed else "✗ DENIED"
        return (f"ScanDecision({status}, "
                f"action={self.action.value if self.action else None}, "
                f"anomaly={self.anomaly_code.value if self.anomaly_code else None})")


@dataclass
class ScanAttempt:
    """Tentative de scan (données brutes).
    
    Encapsule les données brutes d'une tentative de scan
    avant qu'elles ne soient traitées par la machine à états.
    
    Attributs
    ---------
    employee_id : int
        ID de l'employé
    
    site_id : int
        ID du site
    
    current_time : time
        Heure du scan (locale)
    """
    employee_id: int
    site_id: int
    current_time: time
    
    def to_dict(self) -> dict:
        """Pour logs."""
        return {
            'employee_id': self.employee_id,
            'site_id': self.site_id,
            'current_time': self.current_time.isoformat(),
        }
    
    def __repr__(self) -> str:
        return (f"ScanAttempt("
                f"emp={self.employee_id}, "
                f"site={self.site_id}, "
                f"time={self.current_time.strftime('%H:%M')})")
