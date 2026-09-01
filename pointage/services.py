# pointage/services.py
#
# SERVICE CENTRAL DE POINTAGE
# Toutes les vues (web, API, mobile) appellent process_scan().
# Un seul endroit à maintenir et à tester.
#
# Le pointage normal (E1/S1/E2/S2) délègue sa logique métier à la couche
# domaine pure (domain.py + state_machine.py) via l'adaptateur context.py :
#
#   process_scan()
#       -> collect_day_context()      (lecture DB,   pointage/context.py)
#       -> DayStateMachine.decide()   (décision pure, pointage/state_machine.py)
#       -> _apply_scan_decision()     (écriture DB,  ci-dessous)
#
# Les gardes de nuit (_process_garde) restent totalement indépendantes de
# cette logique et ne sont pas concernées par ce flux.

import logging
import uuid
from datetime import time, timedelta, datetime
from django.utils import timezone
from django.db import transaction

from .models import Employe, Site, Pointage, Scan, AnomaliePointage
from .domain import ScanDecision, ScanActionType
from .context import collect_day_context
from .state_machine import DayStateMachine
from .anomalies import enregistrer_anomalie

logger = logging.getLogger(__name__)


# ─── Constantes ──────────────────────────────────────────────────────────────

SEUIL_DOUBLON_SECONDES = 120          # 2 minutes entre deux scans identiques
PLAGE_MIN = time(5, 0)                # Heure minimale autorisée (mode normal uniquement)
PLAGE_MAX = time(23, 0)               # Heure maximale autorisée (mode normal uniquement)
SEUIL_DEPART_ANTICIPE_MINUTES = 15    # Sortie signalée comme anticipée si elle
                                       # intervient au moins ce nombre de minutes
                                       # avant la fermeture officielle du site
                                       # pour la période (matin/après-midi)


# ─── Fonction principale ──────────────────────────────────────────────────────

def process_scan(matricule: str, qr_token: str, site_id: int,
                 mode: str = 'auto', force_new_garde: bool = False) -> dict:
    """
    Point d'entrée unique pour tout scan QR.

    Paramètres
    ----------
    matricule              : str   — extrait du QR code
    qr_token               : str   — UUID extrait du QR code, obligatoire
    site_id                : int   — ID du site de scan
    mode                   : str   — 'auto' (détection auto), 'garde' (nuit)
    force_new_garde        : bool  — True = démarrer nouvelle garde même si une est en cours

    Retour
    ------
    dict avec les clés : status ('success'|'warning'|'error'),
                         code, message, data
    """

    now = timezone.localtime(timezone.now())

    # 1. Valider le QR (matricule + token UUID, sécurité anti-fraude) —
    #    indépendamment du statut actif/inactif de l'employé, pour pouvoir
    #    distinguer "QR invalide" (personne ne correspond) de "employé
    #    inactif" (l'employé existe mais son accès est désactivé) : deux
    #    anomalies de nature différente pour le suivi RH/admin.
    try:
        employe = Employe.objects.get(matricule=matricule, qr_code_token=qr_token)
    except Employe.DoesNotExist:
        enregistrer_anomalie(
            AnomaliePointage.TYPE_INVALID_QR,
            message='QR code invalide (matricule/token non reconnu).',
            matricule_scanne=matricule,
            date_pointage=now.date(),
        )
        return {
            'status': 'error',
            'code': 'QR_INVALIDE',
            'message': 'QR code invalide ou employé inactif.'
        }

    if not employe.actif:
        enregistrer_anomalie(
            AnomaliePointage.TYPE_EMPLOYE_INACTIF,
            message=f"Tentative de scan par un employé inactif ({employe.matricule}).",
            employe=employe,
            date_pointage=now.date(),
        )
        return {
            'status': 'error',
            'code': 'QR_INVALIDE',
            'message': 'QR code invalide ou employé inactif.'
        }

    # 2. Valider le site
    try:
        site = Site.objects.get(id=site_id)
    except Site.DoesNotExist:
        enregistrer_anomalie(
            AnomaliePointage.TYPE_SITE_INVALIDE,
            message=f"Site {site_id} introuvable.",
            employe=employe,
            date_pointage=now.date(),
        )
        return {
            'status': 'error',
            'code': 'SITE_INVALIDE',
            'message': f"Site {site_id} introuvable."
        }

    # 3. Vérifier la plage horaire autorisée (mode normal uniquement —
    #    une garde de nuit se déroule par définition en dehors de cette plage)
    if mode != 'garde' and not (PLAGE_MIN <= now.time() <= PLAGE_MAX):
        message = (
            f"Scan en dehors des heures autorisées "
            f"({PLAGE_MIN.strftime('%Hh%M')}–{PLAGE_MAX.strftime('%Hh%M')})."
        )
        enregistrer_anomalie(
            AnomaliePointage.TYPE_HORS_PLAGE_GLOBALE,
            message=message, employe=employe, site=site, date_pointage=now.date(),
        )
        return {
            'status': 'warning',
            'code': 'HORS_PLAGE',
            'message': message
        }

    # 4. Anti-doublon temporel (protection contre double-scan accidentel)
    dernier_scan = Scan.objects.filter(
        employe=employe,
        timestamp__gte=now - timedelta(seconds=SEUIL_DOUBLON_SECONDES)
    ).order_by('-timestamp').first()

    if dernier_scan:
        elapsed = (now - dernier_scan.timestamp).total_seconds()
        restant = max(1, int(SEUIL_DOUBLON_SECONDES - elapsed))
        message = f"QR déjà scanné. Réessayez dans {restant} seconde(s)."
        enregistrer_anomalie(
            AnomaliePointage.TYPE_DUPLICATE_SCAN,
            message=message, employe=employe, site=site, date_pointage=now.date(),
            contexte={'dernier_scan_id': dernier_scan.id, 'secondes_ecoulees': elapsed},
        )
        return {
            'status': 'warning',
            'code': 'DOUBLON',
            'message': message
        }

    # 5. Router vers la logique garde ou normale
    with transaction.atomic():
        if mode == 'garde':
            return _process_garde(employe, site, now, force_new=force_new_garde)
        else:
            return _process_normal(employe, site, now)


# ─── Logique gardes de nuit ───────────────────────────────────────────────────

def _process_garde(employe, site, now, force_new=False):
    date_courante = now.date()
    heure = now.time()

    # Garde en cours → fin de garde.
    # force_new ne doit ignorer qu'une garde OUVERTE D'UN JOUR PRÉCÉDENT
    # (garde oubliée, non fermée) : c'est son seul usage prévu. Une garde
    # du jour même déjà en cours est TOUJOURS détectée et fermée, jamais
    # ignorée — sinon la branche "nouvelle garde spontanée" plus bas
    # retomberait sur la même clé unique (employe, date_pointage, periode)
    # et lèverait IntegrityError (bug confirmé lors de l'audit).
    garde_en_cours = Pointage.objects.select_for_update().filter(
        employe=employe,
        periode='nuit',
        type_journee='garde',
        heure_depart__isnull=True
    ).order_by('-date_pointage').first()

    if garde_en_cours and force_new and garde_en_cours.date_pointage != date_courante:
        garde_en_cours = None

    if garde_en_cours:
        garde_en_cours.heure_depart = heure
        garde_en_cours.date_depart  = date_courante
        garde_en_cours.save()
        scan = Scan.objects.create(
            employe=employe, site=site,
            timestamp=now, type_scan='fin_garde',
            pointage=garde_en_cours
        )
        return {
            'status': 'success',
            'code': 'fin_garde',
            'message': f"Fin de garde enregistrée à {heure.strftime('%H:%M')}",
            'data': _build_response_data(scan, garde_en_cours, now)
        }

    # Garde planifiée → début de garde
    garde_planifiee = Pointage.objects.select_for_update().filter(
        employe=employe,
        date_pointage=date_courante,
        periode='nuit',
        type_journee='garde',
        heure_arrivee__isnull=True
    ).first()

    if garde_planifiee:
        garde_planifiee.heure_arrivee = heure
        garde_planifiee.site = site
        garde_planifiee.save()
        scan = Scan.objects.create(
            employe=employe, site=site,
            timestamp=now, type_scan='debut_garde',
            pointage=garde_planifiee
        )
        return {
            'status': 'success',
            'code': 'debut_garde',
            'message': f"Début de garde enregistré à {heure.strftime('%H:%M')}",
            'data': _build_response_data(scan, garde_planifiee, now)
        }

    # Nouvelle garde spontanée
    #
    # Pointage a une contrainte unique (employe, date_pointage, periode) :
    # un seul pointage 'nuit' par employé et par date_pointage, même si
    # une garde précédente ce jour-là est déjà clôturée. Une deuxième
    # garde distincte le même jour civil (ex: rappel d'urgence après la
    # fin d'une première garde) ne peut donc pas être créée comme un
    # nouveau Pointage sans violer cette contrainte (IntegrityError
    # confirmé lors de l'audit). Tant que la levée de cette contrainte
    # n'est pas une décision métier explicite, on refuse proprement et on
    # trace l'anomalie plutôt que de laisser planter le scan en 500 —
    # la première garde reste intacte et rien n'est dupliqué.
    garde_deja_cloturee_ce_jour = Pointage.objects.filter(
        employe=employe, date_pointage=date_courante,
        periode='nuit', type_journee='garde',
    ).exclude(heure_depart__isnull=True).exists()

    if garde_deja_cloturee_ce_jour:
        message = (
            "Une garde a déjà été effectuée et clôturée aujourd'hui pour "
            "cet employé. Une deuxième garde distincte le même jour n'est "
            "pas prise en charge automatiquement — contactez un "
            "administrateur."
        )
        enregistrer_anomalie(
            AnomaliePointage.TYPE_GARDE_MULTIPLE_NON_SUPPORTEE,
            message=message, employe=employe, site=site, date_pointage=date_courante,
        )
        return {
            'status': 'warning',
            'code': 'GARDE_MULTIPLE_NON_SUPPORTEE',
            'message': message
        }

    pointage = Pointage.objects.create(
        employe=employe, site=site,
        date_pointage=date_courante,
        periode='nuit', type_journee='garde',
        heure_arrivee=heure, statut='present'
    )
    scan = Scan.objects.create(
        employe=employe, site=site,
        timestamp=now, type_scan='debut_garde',
        pointage=pointage
    )
    return {
        'status': 'success',
        'code': 'debut_garde',
        'message': f"Début de garde enregistré à {heure.strftime('%H:%M')}",
        'data': _build_response_data(scan, pointage, now)
    }


# ─── Logique pointages normaux (E1 → S1 → E2 → S2) ──────────────────────────

def _process_normal(employe, site, now):
    """
    Traite un scan de pointage normal (hors garde de nuit).

    Orchestration pure : cette fonction ne contient elle-même aucune règle
    métier ni aucun accès direct aux champs de Pointage. Elle relie les
    trois couches :

    1. collect_day_context()    — lit l'état réel de la journée en base
                                   (seule fonction autorisée à lire)
    2. DayStateMachine.decide() — décide, sans effet de bord, si le scan
                                   est autorisé et quelle action effectuer
    3. _apply_scan_decision()   — traduit la décision en écriture(s) base
                                   (seule fonction autorisée à écrire)
    """
    date_courante = now.date()

    # lock=True : verrouille les pointages du jour de cet employé pour la
    # durée de la transaction englobante (ouverte par process_scan), afin
    # qu'un second scan concurrent ne parte pas d'un état déjà obsolète.
    context = collect_day_context(
        employee_id=employe.id,
        site=site,
        date_target=date_courante,
        current_time=now.time(),
        lock=True,
    )

    decision = DayStateMachine().decide(context)

    logger.info(
        f"[_process_normal] emp={employe.id} site={site.id} "
        f"time={now.time()} -> {decision}"
    )

    return _apply_scan_decision(decision, employe=employe, site=site, now=now)


# ─── Écriture en base suite à une décision ───────────────────────────────────

def _apply_scan_decision(decision: ScanDecision, employe: Employe, site: Site, now) -> dict:
    """
    Traduit une ScanDecision (déjà prise, immuable) en écriture(s) base.

    Seule fonction autorisée à effectuer des `save()`, `create()`,
    `get_or_create()` ou à ouvrir un `transaction.atomic()` pour le
    pointage normal. Elle ne prend elle-même AUCUNE décision métier :
    elle exécute fidèlement ce que `DayStateMachine.decide()` a décidé.

    Paramètres
    ----------
    decision : ScanDecision
        Décision retournée par DayStateMachine.decide()

    employe : Employe
        Employé concerné (déjà validé par process_scan)

    site : Site
        Site du scan (déjà validé par process_scan)

    now : datetime
        Horodatage du scan (timezone-aware, heure locale)

    Retour
    ------
    dict
        Réponse standard process_scan : status/code/message/[data]
    """
    # ── Scan refusé : rien à écrire côté pointage, mais l'anomalie est
    #    tracée pour suivi administratif ─────────────────────────────────
    if not decision.allowed:
        code = decision.anomaly_code.value if decision.anomaly_code else 'REFUSE'
        logger.info(
            f"[_apply_scan_decision] Refusé pour emp={employe.id} : "
            f"{decision.anomaly_code} - {decision.message}"
        )
        enregistrer_anomalie(
            code,
            message=decision.message,
            employe=employe,
            site=site,
            date_pointage=now.date(),
            contexte=decision.details,
        )
        return {
            'status': 'warning',
            'code': code,
            'message': decision.message,
        }

    # ── Scan autorisé : décision -> écriture ─────────────────────────────
    date_courante = now.date()
    heure = now.time()
    periode = decision.period.value      # 'matin' | 'apres_midi'
    type_scan = decision.action.value    # 'entree_matin', 'sortie_matin', ...
    is_entry = decision.action in (
        ScanActionType.MORNING_ENTRY,
        ScanActionType.AFTERNOON_ENTRY,
    )

    with transaction.atomic():
        pointage, created = Pointage.objects.select_for_update().get_or_create(
            employe=employe,
            date_pointage=date_courante,
            periode=periode,
            defaults={'site': site, 'type_journee': 'normal'}
        )

        if is_entry:
            # Le site est fixé à l'entrée de la période et ne change plus
            # ensuite (règle métier multi-sites : cf. `enregistrer_entree`).
            pointage.enregistrer_entree(heure, site)
        else:
            # Une sortie ne modifie jamais le site : celui de l'entrée fait foi.
            pointage.enregistrer_sortie(heure)
            # Le pointage reste enregistré normalement quoi qu'il arrive
            # (règle métier : une sortie dans la fenêtre autorisée est
            # TOUJOURS acceptée). Ce signalement est un simple ajout
            # d'observation, jamais un blocage — voir docstring de la
            # fonction ci-dessous.
            _detecter_depart_anticipe(pointage, employe, site, periode, heure, now)

        # Scan et pointage dans la même transaction → cohérence garantie
        scan = Scan.objects.create(
            employe=employe, site=site,
            timestamp=now, type_scan=type_scan,
            pointage=pointage
        )

    logger.info(
        f"[_apply_scan_decision] {type_scan} enregistré pour emp={employe.id} "
        f"à {heure.strftime('%H:%M')} (pointage_créé={created})"
    )

    # Le message métier principal (decision.message) est complété par
    # l'avertissement éventuel (decision.warning) — ex. "le matin sera
    # considéré comme absent" lors d'un premier scan directement l'après-midi.
    message = decision.message
    if decision.warning:
        message = f"{message} {decision.warning}"

    return {
        'status': 'success',
        'code': type_scan,
        'message': message,
        'data': _build_response_data(scan, pointage, now)
    }


def _detecter_depart_anticipe(pointage: Pointage, employe: Employe, site: Site,
                               periode: str, heure: time, now) -> None:
    """
    Signale (sans jamais bloquer ni modifier le scan, déjà accepté) une
    sortie intervenue nettement avant la fermeture officielle du site pour
    cette période — ex. sortie matin à 10h alors que le site ferme à 12h.

    Le pointage est déjà enregistré normalement (enregistrer_sortie() a
    été appelé juste avant par l'appelant) ; cette fonction ne fait
    qu'ajouter, en plus, une AnomaliePointage pour suivi et traitement
    administratif (note via anomalies.marquer_traitee / AnomalieTraitement).

    N'est jamais appelée pour les gardes de nuit : _process_garde() est un
    chemin de code entièrement séparé, sans notion de fermeture officielle
    (une garde est par nature ouverte/spontanée).
    """
    _, heure_fermeture = site.get_horaires_pour_periode(periode)
    if not heure_fermeture:
        return

    fermeture_dt = datetime.combine(now.date(), heure_fermeture)
    depart_dt    = datetime.combine(now.date(), heure)
    avance       = fermeture_dt - depart_dt

    seuil_minutes = site.seuil_depart_anticipe_minutes or SEUIL_DEPART_ANTICIPE_MINUTES
    if avance.total_seconds() < seuil_minutes * 60:
        return

    minutes_avance = int(avance.total_seconds() // 60)
    periode_label  = 'matin' if periode == 'matin' else 'après-midi'
    message = (
        f"Sortie {periode_label} enregistrée à {heure.strftime('%H:%M')} sur "
        f"{site.nom}, soit {minutes_avance} min avant la fermeture prévue "
        f"({heure_fermeture.strftime('%H:%M')})."
    )
    enregistrer_anomalie(
        AnomaliePointage.TYPE_DEPART_ANTICIPE,
        message=message,
        employe=employe,
        site=site,
        date_pointage=pointage.date_pointage,
        contexte={
            'periode': periode,
            'heure_depart': heure.isoformat(),
            'heure_fermeture_prevue': heure_fermeture.isoformat(),
            'minutes_avance': minutes_avance,
            'pointage_id': pointage.id,
        },
    )
    logger.info(
        f"[_detecter_depart_anticipe] Signalé pour emp={employe.id} "
        f"pointage={pointage.id} ({minutes_avance} min d'avance)"
    )


def _build_response_data(scan, pointage, now) -> dict:
    """Construit le dictionnaire de réponse standard."""
    return {
        'scan_id':          scan.id,
        'type_scan':        scan.type_scan,
        'type_scan_display': scan.get_type_scan_display(),
        'timestamp':        now.isoformat(),
        'employe': {
            'id':          scan.employe.id,
            'nom_complet': scan.employe.get_nom_complet(),
            'matricule':   scan.employe.matricule,
            'poste':       scan.employe.poste.nom if scan.employe.poste else None,
        },
        'site':             scan.site.nom,
        'periode':          pointage.periode,
        'type_journee':     pointage.type_journee,
        'date':             pointage.date_pointage.isoformat(),
        'heure_arrivee':    str(pointage.heure_arrivee) if pointage.heure_arrivee else None,
        'heure_depart':     str(pointage.heure_depart)  if pointage.heure_depart  else None,
    }


# ─── Parsing du QR code ───────────────────────────────────────────────────────

def parse_qr_data(raw: str) -> dict | None:
    """
    Parse le contenu brut du QR code.
    Format attendu : EMPLOYE:matricule:uuid_token

    split(':', 2) pour gérer les matricules qui contiendraient des ':'.
    Retourne {'matricule': ..., 'token': ...} ou None si invalide.

    Le token est validé comme UUID ici (pas seulement "non vide") : le
    champ Employe.qr_code_token est un UUIDField, et une valeur mal
    formée levait auparavant une ValidationError non catchée jusqu'à la
    base de données (500). En la rejetant dès le parsing, un QR invalide
    produit toujours une réponse métier propre (QR invalide), jamais un 500.
    """
    parts = raw.strip().split(':', 2)
    if len(parts) != 3 or parts[0] != 'EMPLOYE':
        return None
    matricule, token = parts[1], parts[2]
    try:
        uuid.UUID(token)
    except (ValueError, AttributeError, TypeError):
        return None
    return {'matricule': matricule, 'token': token}