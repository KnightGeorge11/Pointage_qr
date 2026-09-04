# pointage/services.py
#
# SERVICE CENTRAL DE POINTAGE
# Toutes les vues (web, API, mobile) appellent process_scan().
# Un seul endroit à maintenir et à tester.

import logging
import uuid
import re
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


def parse_qr_data(qr_string: str) -> dict | None:
    """Parse et valide un QR code au format EMPLOYE:matricule:token.
    
    Retour: {'matricule': str, 'token': str} ou None si invalide
    """
    if not qr_string or not isinstance(qr_string, str):
        return None
    
    qr_string = qr_string.strip()
    if not qr_string.startswith('EMPLOYE:'):
        return None
    
    parts = qr_string.split(':')
    if len(parts) != 3:
        return None
    
    prefix, matricule, token = parts
    matricule = matricule.strip()
    token = token.strip()
    
    if not matricule or len(matricule) > 50:
        return None
    if not re.match(r'^[a-zA-Z0-9\-_]+$', matricule):
        return None
    
    try:
        uuid.UUID(token)
    except (ValueError, AttributeError, TypeError):
        return None
    
    return {'matricule': matricule, 'token': token}


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
    """Point d'entrée unique pour tout scan QR.
    
    Tous les paramètres sont validés côté serveur.
    Le serveur décide lui-même du résultat, jamais le client.
    """
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
                        'message': "L'identifiant d'événement a déjà été utilisé pour un autre employé ou site.",
                    }
                return _build_response_data(existing_scan, existing_scan.pointage, now) | {
                    'status': 'success',
                    'code': existing_scan.type_scan,
                }

        # La suite du service conserve la machine d'état existante du dépôt.
        # Cette portion est inchangée dans la branche courante.
