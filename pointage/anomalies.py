import logging
from typing import Optional

from django.db import transaction
from django.utils import timezone

from .models import AnomaliePointage, AnomalieTraitement, Employe, Site, Pointage, CustomUser

logger = logging.getLogger(__name__)


# Types représentant un blocage d'ÉTAT PERSISTANT (voir docstring de
# enregistrer_anomalie ci-dessous pour la distinction avec les refus
# ponctuels, jamais dédupliqués).
DEDUP_TYPES = frozenset({
    AnomaliePointage.TYPE_MISSING_MORNING_EXIT,
    AnomaliePointage.TYPE_GARDE_MULTIPLE_NON_SUPPORTEE,
    AnomaliePointage.TYPE_DAY_COMPLETE,
    AnomaliePointage.TYPE_TRANSITION_IMPOSSIBLE,
    AnomaliePointage.TYPE_INVALID_STATE,
})


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

    Déduplique — UNIQUEMENT pour les types qui représentent un blocage
    d'ÉTAT PERSISTANT (voir DEDUP_TYPES ci-dessous) : tant que rien n'a
    changé en base, retenter donne exactement la même anomalie sous-jacente
    (cas typique : sortie matin manquante, retentée plusieurs fois). Sans
    ça, un employé bloqué créait autant de lignes identiques que de
    tentatives, polluant la liste des anomalies à traiter par l'admin pour
    un seul et même problème.

    Les autres types (during_break, outside_hours, duplicate_scan, etc.)
    ne sont PAS dédupliqués : ce sont des refus ponctuels liés au moment
    précis du scan, pas à un état persistant — plusieurs tentatives à des
    moments distincts de la même journée sont des événements réels et
    distincts, qui méritent chacun leur propre trace.

    Ne lève jamais d'exception métier : l'enregistrement d'une anomalie
    ne doit jamais empêcher process_scan() de répondre à l'utilisateur.
    En cas d'échec d'écriture, l'erreur est journalisée puis ravalée.
    """
    contexte = contexte or {}
    try:
        if type_anomalie in DEDUP_TYPES:
            cle_lookup = {
                'type': type_anomalie,
                'statut': AnomaliePointage.STATUT_OUVERTE,
                'date_pointage': date_pointage,
            }
            if employe:
                cle_lookup['employe'] = employe
            else:
                cle_lookup['matricule_scanne'] = matricule_scanne or ''

            existante = AnomaliePointage.objects.filter(**cle_lookup).order_by('-created_at').first()
            if existante:
                existante.contexte = {
                    **existante.contexte,
                    **contexte,
                    'tentatives': existante.contexte.get('tentatives', 1) + 1,
                    'derniere_tentative': timezone.now().isoformat(),
                    'dernier_site_tente': site.nom if site else existante.contexte.get('dernier_site_tente'),
                }
                existante.save(update_fields=['contexte'])
                logger.info(
                    f"[enregistrer_anomalie] {type_anomalie} déjà ouverte (id={existante.id}) — "
                    f"tentative supplémentaire tracée, pas de doublon créé"
                )
                return existante

        anomalie = AnomaliePointage.objects.create(
            type=type_anomalie,
            employe=employe,
            matricule_scanne=matricule_scanne or (employe.matricule if employe else ''),
            site=site,
            date_pointage=date_pointage,
            message=message,
            contexte=contexte,
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
    type_action: str = 'correction',
) -> AnomalieTraitement:
    """
    Marque une anomalie comme traitée et conserve la trace du traitement.

    Paramètres
    ----------
    type_action
        Une des valeurs AnomalieTraitement.ACTION_* (correction /
        justification / rejet) — l'action RH réellement posée. Ne pas
        confondre avec AnomaliePointage.statut.

    Lève
    ----
    PermissionError
        Si l'utilisateur n'est pas Admin/RH (is_staff).
    ValueError
        Si l'anomalie est déjà clôturée, ou si type_action est invalide.
    """
    # Vérification des permissions - Seul l'Admin/RH peut traiter une anomalie
    if not administrateur.is_staff:
        raise PermissionError("Seul un administrateur ou RH peut traiter une anomalie.")

    if anomalie.statut == AnomaliePointage.STATUT_CLOTUREE:
        raise ValueError("Impossible de retraiter une anomalie déjà clôturée.")

    valides = {choice for choice, _ in AnomalieTraitement.TYPE_ACTION_CHOICES}
    if type_action not in valides:
        raise ValueError(f"type_action invalide : {type_action!r}")

    with transaction.atomic():
        traitement, created = AnomalieTraitement.objects.update_or_create(
            anomalie=anomalie,
            defaults={
                'administrateur': administrateur,
                'commentaire': commentaire,
                'corrections': corrections or [],
                'pointage_concerne': pointage_concerne,
                'type_action': type_action,
            }
        )
        anomalie.statut = AnomaliePointage.STATUT_TRAITEE
        anomalie.save(update_fields=['statut'])

    logger.info(
        f"[marquer_traitee] anomalie={anomalie.id} traitée ({type_action}) par "
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