# pointage/anomalies.py
#
# COUCHE DE PERSISTANCE DES ANOMALIES (Phase 4)
# ================================================
#
# Cette couche est posée AU-DESSUS du moteur métier de la Phase 3
# (domain.py / state_machine.py / context.py / services.py) et ne le
# modifie jamais. Elle se contente d'enregistrer, après coup, ce que
# le moteur a déjà décidé.
#
# Deux points d'appel, tous deux dans services.py :
#   1. process_scan()        — pré-contrôles (QR invalide, employé
#                               inactif, site invalide, hors plage
#                               globale, doublon), AVANT la machine à états
#   2. _apply_scan_decision() — quand decision.allowed est False
#
# Ce module ne prend AUCUNE décision métier : il transforme un événement
# déjà survenu en ligne de base persistée, consultable et traitable par
# un administrateur.

import logging
from typing import Optional

from django.db import transaction
from django.utils import timezone

from .models import AnomaliePointage, AnomalieTraitement, Employe, Site, Pointage, CustomUser

logger = logging.getLogger(__name__)


# ─── Création ────────────────────────────────────────────────────────────────

def enregistrer_anomalie(
    type_anomalie: str,
    message: str,
    employe: Optional[Employe] = None,
    matricule_scanne: str = '',
    site: Optional[Site] = None,
    date_pointage=None,
    contexte: Optional[dict] = None,
) -> AnomaliePointage:
    """
    Enregistre une anomalie détectée lors d'un scan.

    Ne lève jamais d'exception métier : l'enregistrement d'une anomalie
    ne doit jamais empêcher process_scan() de répondre à l'utilisateur.
    En cas d'échec d'écriture, l'erreur est journalisée puis ravalée.

    Paramètres
    ----------
    type_anomalie : str
        Une des valeurs de AnomaliePointage.TYPE_CHOICES.

    message : str
        Message déjà produit par le moteur métier (decision.message /
        message de refus de process_scan), affiché tel quel à l'admin.

    employe : Employe, optional
        Employé concerné, si identifié.

    matricule_scanne : str, optional
        Matricule brut du QR scanné (utile quand `employe` est None,
        ex: QR invalide).

    site : Site, optional
        Site du scan, si connu.

    date_pointage : date, optional
        Date métier concernée (peut différer de la date de création si
        pertinent un jour ; aujourd'hui toujours la date du scan).

    contexte : dict, optional
        Détails supplémentaires (ex: `decision.details`) conservés pour
        analyse ultérieure.

    Retour
    ------
    AnomaliePointage
        L'anomalie créée (ou une instance non sauvegardée si l'écriture
        a échoué — ne jamais compter dessus pour une logique métier).
    """
    try:
        anomalie = AnomaliePointage.objects.create(
            type=type_anomalie,
            employe=employe,
            matricule_scanne=matricule_scanne or (employe.matricule if employe else ''),
            site=site,
            date_pointage=date_pointage,
            message=message,
            contexte=contexte or {},
        )
        logger.info(
            f"[enregistrer_anomalie] {type_anomalie} créée (id={anomalie.id}) "
            f"emp={employe.id if employe else matricule_scanne!r}"
        )
        return anomalie
    except Exception:
        # L'enregistrement d'une anomalie est un effet de bord d'observation :
        # son échec ne doit jamais faire échouer un scan.
        logger.exception(
            f"[enregistrer_anomalie] Échec de l'enregistrement pour type={type_anomalie}"
        )
        return AnomaliePointage(
            type=type_anomalie, employe=employe,
            matricule_scanne=matricule_scanne, site=site,
            date_pointage=date_pointage, message=message,
            contexte=contexte or {},
        )


# ─── Traitement / clôture (actions administrateur) ───────────────────────────

def marquer_traitee(
    anomalie: AnomaliePointage,
    administrateur: CustomUser,
    commentaire: str = '',
    corrections: Optional[list] = None,
    pointage_concerne: Optional[Pointage] = None,
) -> AnomalieTraitement:
    """
    Marque une anomalie comme traitée et conserve la trace du traitement.

    Paramètres
    ----------
    anomalie : AnomaliePointage
        L'anomalie à traiter.

    administrateur : CustomUser
        L'utilisateur effectuant le traitement.

    commentaire : str, optional
        Explication de la résolution.

    corrections : list[dict], optional
        Liste de corrections effectuées, ex :
        [{'champ': 'heure_depart', 'ancienne_valeur': None, 'nouvelle_valeur': '12:05'}]

    pointage_concerne : Pointage, optional
        Le pointage corrigé, si une correction de pointage a été réalisée.

    Retour
    ------
    AnomalieTraitement

    Lève
    ----
    PermissionError
        Si l'utilisateur n'est pas Admin/RH (is_staff).
    ValueError
        Si l'anomalie est déjà clôturée.
    """
    # Vérification des permissions - Seul l'Admin/RH peut traiter une anomalie
    if not administrateur.is_staff:
        raise PermissionError("Seul un administrateur ou RH peut traiter une anomalie.")

    if anomalie.statut == AnomaliePointage.STATUT_CLOTUREE:
        raise ValueError("Impossible de retraiter une anomalie déjà clôturée.")

    with transaction.atomic():
        traitement, _ = AnomalieTraitement.objects.update_or_create(
            anomalie=anomalie,
            defaults={
                'administrateur': administrateur,
                'commentaire': commentaire,
                'corrections': corrections or [],
                'pointage_concerne': pointage_concerne,
            }
        )
        anomalie.statut = AnomaliePointage.STATUT_TRAITEE
        anomalie.save(update_fields=['statut'])

    logger.info(
        f"[marquer_traitee] anomalie={anomalie.id} traitée par "
        f"{administrateur} ({len(corrections or [])} correction(s))"
    )
    return traitement


def marquer_cloturee(anomalie: AnomaliePointage, administrateur: CustomUser) -> AnomaliePointage:
    """
    Clôture une anomalie déjà traitée.

    Lève
    ----
    PermissionError
        Si l'utilisateur n'est pas Admin/RH (is_staff).
    ValueError
        Si l'anomalie n'a pas encore été traitée (statut != 'traitee').
    """
    # Vérification des permissions - Seul l'Admin/RH peut clôturer une anomalie
    if not administrateur.is_staff:
        raise PermissionError("Seul un administrateur ou RH peut clôturer une anomalie.")

    if anomalie.statut == AnomaliePointage.STATUT_OUVERTE:
        raise ValueError("Impossible de clôturer une anomalie qui n'a pas été traitée.")
    if anomalie.statut == AnomaliePointage.STATUT_CLOTUREE:
        return anomalie

    anomalie.statut = AnomaliePointage.STATUT_CLOTUREE
    anomalie.cloturee_par = administrateur
    anomalie.date_cloture = timezone.now()
    anomalie.save(update_fields=['statut', 'cloturee_par', 'date_cloture'])

    logger.info(f"[marquer_cloturee] anomalie={anomalie.id} clôturée par {administrateur}")
    return anomalie


# ─── Lecture (helpers pour vues / dashboard) ─────────────────────────────────

def compter_anomalies_ouvertes() -> int:
    """Nombre d'anomalies au statut 'ouverte' — pour badge/compteur dashboard."""
    return AnomaliePointage.objects.filter(statut=AnomaliePointage.STATUT_OUVERTE).count()