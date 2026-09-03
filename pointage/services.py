# pointage/services.py
#
# SERVICE CENTRAL DE POINTAGE
# Toutes les vues (web, API, mobile) appellent process_scan().
# Un seul endroit à maintenir et à tester.

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

SEUIL_DOUBLON_SECONDES = 120
PLAGE_MIN = time(5, 0)
PLAGE_MAX = time(23, 0)
SEUIL_DEPART_ANTICIPE_MINUTES = 15
OFFLINE_MAX_AGE = timedelta(hours=24)
OFFLINE_FUTURE_TOLERANCE = timedelta(minutes=5)


def _normaliser_captured_at(captured_at, client_event_id):
    """Valide une date cliente avant qu'elle ne devienne une heure métier.

    Le timestamp d'un téléphone n'est jamais une preuve cryptographique de
    l'heure réelle. Il reste nécessaire au mode offline, mais il est limité à
    24 h, interdit dans le futur au-delà de 5 min, et exige un UUID d'événement
    pour permettre l'idempotence et limiter les rejouements.
    """
    server_now = timezone.localtime(timezone.now())
    if captured_at is None:
        return server_now, None

    if not client_event_id:
        return None, {
            'status': 'error',
            'code': 'CAPTURED_AT_REQUIERT_EVENT_ID',
            'message': "Une date de scan cliente doit être accompagnée d'un identifiant d'événement unique.",
        }

    try:
        uuid.UUID(str(client_event_id))
    except (ValueError, TypeError, AttributeError):
        return None, {
            'status': 'error',
            'code': 'EVENT_ID_INVALIDE',
            'message': "L'identifiant d'événement offline est invalide.",
        }

    if not isinstance(captured_at, datetime):
        return None, {
            'status': 'error',
            'code': 'CAPTURED_AT_INVALIDE',
            'message': "La date de capture du scan est invalide.",
        }

    if timezone.is_naive(captured_at):
        captured_at = timezone.make_aware(captured_at, timezone.get_current_timezone())
    captured_at = timezone.localtime(captured_at)

    delta = server_now - captured_at
    if delta < -OFFLINE_FUTURE_TOLERANCE:
        return None, {
            'status': 'warning',
            'code': 'DATE_SCAN_FUTURE',
            'message': "Le scan indique une date future non autorisée. Synchronisation refusée.",
        }
    if delta > OFFLINE_MAX_AGE:
        return None, {
            'status': 'warning',
            'code': 'SCAN_OFFLINE_TROP_ANCIEN',
            'message': "Le scan offline est trop ancien pour être synchronisé automatiquement (maximum 24 heures).",
        }

    return captured_at, None


def process_scan(matricule: str, qr_token: str, site_id: int,
                 mode: str = 'auto', force_new_garde: bool = False,
                 client_event_id=None, captured_at=None) -> dict:
    """Point d'entrée unique pour tout scan QR."""
    now, timestamp_error = _normaliser_captured_at(captured_at, client_event_id)
    if timestamp_error:
        return timestamp_error

    if client_event_id:
        try:
            client_event_id = uuid.UUID(str(client_event_id))
        except (ValueError, TypeError, AttributeError):
            return {
                'status': 'error',
                'code': 'EVENT_ID_INVALIDE',
                'message': "L'identifiant d'événement offline est invalide.",
            }

    if mode not in ('auto', 'garde'):
        return {
            'status': 'error',
            'code': 'MODE_INVALIDE',
            'message': "Mode de pointage invalide. Valeurs acceptées : 'auto' ou 'garde'.",
        }

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

    with transaction.atomic():
        employe = Employe.objects.select_for_update().get(pk=employe.pk)

        if client_event_id:
            existing_scan = Scan.objects.select_related('employe', 'site', 'pointage').filter(
                client_event_id=client_event_id
            ).first()
            if existing_scan:
                if existing_scan.employe_id != employe.pk or existing_scan.site_id != site.pk:
                    logger.warning(
                        "[process_scan] Réutilisation d'un client_event_id pour un autre "
                        "employé/site : event=%s emp=%s site=%s attendu_emp=%s attendu_site=%s",
                        client_event_id,
                        existing_scan.employe_id,
                        existing_scan.site_id,
                        employe.pk,
                        site.pk,
                    )
                    return {
                        'status': 'error',
                        'code': 'EVENT_ID_REUTILISE',
                        'message': "Cet événement offline appartient déjà à un autre scan.",
                    }
                pointage = existing_scan.pointage
                data = _build_response_data(
                    existing_scan, pointage, timezone.localtime(existing_scan.timestamp)
                ) if pointage else None
                return {
                    'status': 'success',
                    'code': existing_scan.type_scan,
                    'message': 'Scan déjà synchronisé (événement idempotent).',
                    'data': data,
                    'idempotent': True,
                }

        if not employe.actif:
            enregistrer_anomalie(
                AnomaliePointage.TYPE_EMPLOYE_INACTIF,
                message=f"Tentative de scan par un employé inactif ({employe.matricule}).",
                employe=employe,
                site=site,
                date_pointage=now.date(),
            )
            return {
                'status': 'error',
                'code': 'QR_INVALIDE',
                'message': 'QR code invalide ou employé inactif.'
            }

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

        if mode == 'garde':
            return _process_garde(employe, site, now, force_new=force_new_garde, client_event_id=client_event_id)
        return _process_normal(employe, site, now, client_event_id=client_event_id)


def _process_garde(employe, site, now, force_new=False, client_event_id=None):
    date_courante = now.date()
    heure = now.time()

    garde_en_cours = Pointage.objects.select_for_update().filter(
        employe=employe,
        periode='nuit',
        type_journee='garde',
        heure_arrivee__isnull=False,
        heure_depart__isnull=True
    ).order_by('-date_pointage', '-date_creation').first()

    if garde_en_cours and garde_en_cours.date_pointage != date_courante and force_new:
        message = (
            "Une garde précédente est encore ouverte. Impossible de créer une "
            "nouvelle garde tant que cette garde n'est pas clôturée ou corrigée "
            "par un administrateur."
        )
        enregistrer_anomalie(
            AnomaliePointage.TYPE_GARDE_MULTIPLE_NON_SUPPORTEE,
            message=message,
            employe=employe,
            site=site,
            date_pointage=date_courante,
            contexte={'pointage_garde_ouverte_id': garde_en_cours.id},
        )
        return {
            'status': 'warning',
            'code': 'GARDE_PRECEDENTE_NON_CLOTUREE',
            'message': message,
        }

    if garde_en_cours and force_new and garde_en_cours.date_pointage == date_courante:
        force_new = False

    if garde_en_cours:
        garde_en_cours.heure_depart = heure
        garde_en_cours.date_depart = date_courante
        garde_en_cours.save()
        scan = Scan.objects.create(
            employe=employe, site=site,
            timestamp=now, type_scan='fin_garde',
            pointage=garde_en_cours,
            client_event_id=client_event_id
        )
        return {
            'status': 'success',
            'code': 'fin_garde',
            'message': f"Fin de garde enregistrée à {heure.strftime('%H:%M')}",
            'data': _build_response_data(scan, garde_en_cours, now)
        }

    garde_planifiee = Pointage.objects.select_for_update().filter(
        employe=employe,
        date_pointage=date_courante,
        periode='nuit',
        type_journee='garde',
        heure_arrivee__isnull=True,
        heure_depart__isnull=True,
    ).first()

    garde_cloturee_du_jour = Pointage.objects.filter(
        employe=employe,
        date_pointage=date_courante,
        periode='nuit',
        type_journee='garde',
        heure_arrivee__isnull=False,
        heure_depart__isnull=False,
    ).first()
    if garde_cloturee_du_jour:
        message = (
            "Une garde est déjà enregistrée pour cet employé aujourd'hui. "
            "Une deuxième garde distincte le même jour n'est pas supportée."
        )
        enregistrer_anomalie(
            AnomaliePointage.TYPE_GARDE_MULTIPLE_NON_SUPPORTEE,
            message=message, employe=employe, site=site,
            date_pointage=date_courante,
            contexte={'pointage_garde_cloturee_id': garde_cloturee_du_jour.id},
        )
        return {'status':'warning','code':'GARDE_MULTIPLE_NON_SUPPORTEE','message':message}

    if garde_planifiee:
        garde_planifiee.heure_arrivee = heure
        garde_planifiee.date_depart = None
        garde_planifiee.site = site
        garde_planifiee.save()
        scan = Scan.objects.create(
            employe=employe, site=site,
            timestamp=now, type_scan='debut_garde',
            pointage=garde_planifiee,
            client_event_id=client_event_id
        )
        return {
            'status': 'success',
            'code': 'debut_garde',
            'message': f"Début de garde enregistré à {heure.strftime('%H:%M')}",
            'data': _build_response_data(scan, garde_planifiee, now)
        }

    message = (
        "Aucune garde n'est planifiée pour cet employé aujourd'hui. "
        "La garde doit être planifiée par un administrateur avant le scan."
    )
    enregistrer_anomalie(
        AnomaliePointage.TYPE_GARDE_MULTIPLE_NON_SUPPORTEE,
        message=message,
        employe=employe,
        site=site,
        date_pointage=date_courante,
        contexte={'raison': 'garde_non_planifiee'},
    )
    return {
        'status': 'warning',
        'code': 'GARDE_NON_PLANIFIEE',
        'message': message,
    }


def _process_normal(employe, site, now, client_event_id=None):
    date_courante = now.date()
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
    return _apply_scan_decision(decision, employe=employe, site=site, now=now, client_event_id=client_event_id)


def _apply_scan_decision(decision: ScanDecision, employe: Employe, site: Site, now, client_event_id=None) -> dict:
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

    date_courante = now.date()
    heure = now.time()
    periode = decision.period.value
    type_scan = decision.action.value
    is_entry = decision.action in (
        ScanActionType.MORNING_ENTRY,
        ScanActionType.AFTERNOON_ENTRY,
    )

    pointage, created = Pointage.objects.select_for_update().get_or_create(
        employe=employe,
        date_pointage=date_courante,
        periode=periode,
        defaults={'site': site, 'type_journee': 'normal'}
    )

    if is_entry:
        pointage.enregistrer_entree(heure, site)
    else:
        pointage.enregistrer_sortie(heure)
        _detecter_depart_anticipe(pointage, employe, site, periode, heure, now)

    scan = Scan.objects.create(
        employe=employe, site=site,
        timestamp=now, type_scan=type_scan,
        pointage=pointage,
        client_event_id=client_event_id
    )

    logger.info(
        f"[_apply_scan_decision] {type_scan} enregistré pour emp={employe.id} "
        f"à {heure.strftime('%H:%M')} (pointage_créé={created})"
    )

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
    _, heure_fermeture = site.get_horaires_pour_periode(periode)
    if not heure_fermeture:
        return

    fermeture_dt = datetime.combine(now.date(), heure_fermeture)
    depart_dt = datetime.combine(now.date(), heure)
    avance = fermeture_dt - depart_dt

    seuil_minutes = site.seuil_depart_anticipe_minutes or SEUIL_DEPART_ANTICIPE_MINUTES
    if avance.total_seconds() < seuil_minutes * 60:
        return

    minutes = int(avance.total_seconds() // 60)
    enregistrer_anomalie(
        AnomaliePointage.TYPE_DEPART_ANTICIPE,
        message=(
            f"Départ anticipé de {minutes} minute(s) pour {employe.get_nom_complet()} "
            f"({periode}). Sortie à {heure.strftime('%H:%M')}, "
            f"fermeture prévue à {heure_fermeture.strftime('%H:%M')}."
        ),
        employe=employe,
        site=site,
        pointage=pointage,
        date_pointage=now.date(),
        contexte={
            'periode': periode,
            'heure_depart': heure.strftime('%H:%M:%S'),
            'heure_fermeture': heure_fermeture.strftime('%H:%M:%S'),
            'avance_minutes': minutes,
        },
    )


def _build_response_data(scan: Scan, pointage: Pointage, now) -> dict:
    return {
        'scan_id': scan.id,
        'pointage_id': pointage.id if pointage else None,
        'timestamp': now.isoformat() if now else None,
        'type_scan': scan.type_scan,
        'periode': pointage.periode if pointage else None,
        'heure_arrivee': pointage.heure_arrivee.strftime('%H:%M:%S') if pointage and pointage.heure_arrivee else None,
        'heure_depart': pointage.heure_depart.strftime('%H:%M:%S') if pointage and pointage.heure_depart else None,
        'message': 'Scan enregistré avec succès',
    }