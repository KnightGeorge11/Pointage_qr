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


def process_scan(matricule: str, qr_token: str, site_id: int,
                 mode: str = 'auto', force_new_garde: bool = False) -> dict:
    """Point d'entrée unique pour tout scan QR."""
    now = timezone.localtime(timezone.now())

    # Le contrat central n'accepte que ces deux modes. Les couches API
    # valident déjà ce champ, mais le service doit aussi se protéger lorsqu'il
    # est appelé directement (web, tests, scripts, tâches internes).
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

    # Le verrou de ligne employé englobe le contrôle d'activité, l'anti-
    # doublon et toute la transition de pointage. Deux requêtes simultanées
    # pour le même badge ne peuvent donc plus toutes les deux passer le
    # contrôle "dernier scan" avant d'écrire.
    with transaction.atomic():
        employe = Employe.objects.select_for_update().get(pk=employe.pk)

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
            return _process_garde(employe, site, now, force_new=force_new_garde)
        return _process_normal(employe, site, now)


def _process_garde(employe, site, now, force_new=False):
    date_courante = now.date()
    heure = now.time()

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
        garde_en_cours.date_depart = date_courante
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

    garde_deja_cloturee_ce_jour = Pointage.objects.filter(
        employe=employe, date_pointage=date_courante,
        periode='nuit', type_journee='garde',
    ).exclude(heure_depart__isnull=True).exists()

    if garde_deja_cloturee_ce_jour:
        message = (
            "Une garde a déjà été effectuée et clôturée aujourd'hui pour "
            "cet employé. Une deuxième garde distincte le même jour n'est "
            "pas prise en charge automatiquement — contactez un administrateur."
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


def _process_normal(employe, site, now):
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
    return _apply_scan_decision(decision, employe=employe, site=site, now=now)


def _apply_scan_decision(decision: ScanDecision, employe: Employe, site: Site, now) -> dict:
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
        pointage=pointage
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

    minutes_avance = int(avance.total_seconds() // 60)
    periode_label = 'matin' if periode == 'matin' else 'après-midi'
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
    return {
        'scan_id': scan.id,
        'type_scan': scan.type_scan,
        'type_scan_display': scan.get_type_scan_display(),
        'timestamp': now.isoformat(),
        'employe': {
            'id': scan.employe.id,
            'nom_complet': scan.employe.get_nom_complet(),
            'matricule': scan.employe.matricule,
            'poste': scan.employe.poste.nom if scan.employe.poste else None,
        },
        'site': scan.site.nom,
        'periode': pointage.periode,
        'type_journee': pointage.type_journee,
        'date': pointage.date_pointage.isoformat(),
        'heure_arrivee': str(pointage.heure_arrivee) if pointage.heure_arrivee else None,
        'heure_depart': str(pointage.heure_depart) if pointage.heure_depart else None,
    }


def parse_qr_data(raw: str) -> dict | None:
    """Parse EMPLOYE:matricule:uuid_token et valide le token UUID."""
    parts = raw.strip().split(':', 2)
    if len(parts) != 3 or parts[0] != 'EMPLOYE':
        return None
    matricule, token = parts[1], parts[2]
    try:
        uuid.UUID(token)
    except (ValueError, AttributeError, TypeError):
        return None
    return {'matricule': matricule, 'token': token}
