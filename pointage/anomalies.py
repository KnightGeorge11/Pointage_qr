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

    Les anomalies correspondant à un état persistant sont dédupliquées.
    Les refus ponctuels restent des événements distincts.

    L'enregistrement d'une anomalie ne doit jamais empêcher process_scan()
    de répondre à l'utilisateur : les erreurs sont journalisées et ravalées.
    """
    contexte = contexte or {}
    try:
        if type_anomalie in DEDUP_TYPES:
            # Verrouiller l'employé avant la recherche rend la séquence
            # recherche/création atomique entre deux scans concurrents du
            # même employé. Sans ce verrou, deux transactions pouvaient
            # toutes deux constater l'absence d'anomalie et créer un doublon.
            employe_verrouille = None
            if employe:
                employe_verrouille = Employe.objects.select_for_update().get(pk=employe.pk)

            cle_lookup = {
                'type': type_anomalie,
                'statut': AnomaliePointage.STATUT_OUVERTE,
                'date_pointage': date_pointage,
            }
            if employe_verrouille:
                cle_lookup['employe'] = employe_verrouille
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
        logger.exception(
            f"[enregistrer_anomalie] Échec de l'enregistrement pour type={type_anomalie}"
        )
        return AnomaliePointage(
            type=type_anomalie, employe=employe,
            matricule_scanne=matricule_scanne, site=site,
            date_pointage=date_pointage, message=message,
            contexte=contexte or {},
        )


def marquer_traitee(
    anomalie: AnomaliePointage,
    administrateur: CustomUser,
    commentaire: str = '',
    corrections: Optional[list] = None,
    pointage_concerne: Optional[Pointage] = None,
    type_action: str = 'correction',
) -> AnomalieTraitement:
    """Marque une anomalie comme traitée et conserve la trace du traitement."""
    if not administrateur.is_staff:
        raise PermissionError("Seul un administrateur ou RH peut traiter une anomalie.")

    commentaire = (commentaire or '').strip()
    if not commentaire:
        raise ValueError("Un commentaire est obligatoire pour traiter une anomalie.")

    valides = {choice for choice, _ in AnomalieTraitement.TYPE_ACTION_CHOICES}
    if type_action not in valides:
        raise ValueError(f"type_action invalide : {type_action!r}")

    with transaction.atomic():
        anomalie_db = AnomaliePointage.objects.select_for_update().get(pk=anomalie.pk)
        if anomalie_db.statut == AnomaliePointage.STATUT_CLOTUREE:
            raise ValueError("Impossible de retraiter une anomalie déjà clôturée.")

        traitement, created = AnomalieTraitement.objects.update_or_create(
            anomalie=anomalie_db,
            defaults={
                'administrateur': administrateur,
                'commentaire': commentaire,
                'corrections': corrections or [],
                'pointage_concerne': pointage_concerne,
                'type_action': type_action,
            }
        )
        anomalie_db.statut = AnomaliePointage.STATUT_TRAITEE
        anomalie_db.save(update_fields=['statut'])
        anomalie = anomalie_db

    logger.info(
        f"[marquer_traitee] anomalie={anomalie.id} traitée ({type_action}) par "
        f"{administrateur} ({len(corrections or [])} correction(s))"
    )
    return traitement


def marquer_cloturee(anomalie: AnomaliePointage, administrateur: CustomUser) -> AnomaliePointage:
    """Clôture une anomalie déjà traitée."""
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


def compter_anomalies_ouvertes() -> int:
    """Nombre d'anomalies au statut 'ouverte' — pour badge/compteur dashboard."""
    return AnomaliePointage.objects.filter(statut=AnomaliePointage.STATUT_OUVERTE).count()
