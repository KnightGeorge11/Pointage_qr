import logging
from typing import Optional

from django.db import transaction
from django.utils import timezone

from .models import AnomaliePointage, AnomalieTraitement, Employe, Site, Pointage, CustomUser

logger = logging.getLogger(__name__)


# Classification metier centralisee : une anomalie n'implique pas toujours
# le meme comportement du scan.
CATEGORIE_SECURITE = 'securite'
CATEGORIE_BLOQUANTE = 'bloquante'
CATEGORIE_RH = 'rh'

ANOMALIES_SECURITE = frozenset({
    AnomaliePointage.TYPE_INVALID_QR,
    AnomaliePointage.TYPE_EMPLOYE_INACTIF,
    AnomaliePointage.TYPE_SITE_INVALIDE,
})

ANOMALIES_BLOQUANTES = frozenset({
    AnomaliePointage.TYPE_DUPLICATE_SCAN,
    AnomaliePointage.TYPE_OUTSIDE_HOURS,
    AnomaliePointage.TYPE_DURING_BREAK,
    AnomaliePointage.TYPE_DAY_COMPLETE,
    AnomaliePointage.TYPE_MISSING_MORNING_EXIT,
    AnomaliePointage.TYPE_TRANSITION_IMPOSSIBLE,
    AnomaliePointage.TYPE_INVALID_STATE,
    AnomaliePointage.TYPE_HORS_PLAGE_GLOBALE,
    AnomaliePointage.TYPE_GARDE_MULTIPLE_NON_SUPPORTEE,
})

ANOMALIES_RH = frozenset({
    AnomaliePointage.TYPE_DEPART_ANTICIPE,
})

# Ces anomalies sont regroupees tant qu'une anomalie ouverte du meme type,
# employe et jour existe deja.
DEDUP_TYPES = frozenset({
    AnomaliePointage.TYPE_MISSING_MORNING_EXIT,
    AnomaliePointage.TYPE_GARDE_MULTIPLE_NON_SUPPORTEE,
    AnomaliePointage.TYPE_DAY_COMPLETE,
    AnomaliePointage.TYPE_TRANSITION_IMPOSSIBLE,
    AnomaliePointage.TYPE_INVALID_STATE,
})


def categorie_anomalie(type_anomalie: str) -> str:
    """Retourne la categorie canonique : securite, bloquante ou RH."""
    if type_anomalie in ANOMALIES_SECURITE:
        return CATEGORIE_SECURITE
    if type_anomalie in ANOMALIES_RH:
        return CATEGORIE_RH
    if type_anomalie in ANOMALIES_BLOQUANTES:
        return CATEGORIE_BLOQUANTE
    # Fail-safe : un nouveau type inconnu ne doit jamais etre traite comme
    # une simple anomalie RH non bloquante.
    return CATEGORIE_BLOQUANTE


def anomalie_est_bloquante(type_anomalie: str) -> bool:
    """Indique si le scan associe doit etre refuse."""
    return categorie_anomalie(type_anomalie) in {
        CATEGORIE_SECURITE,
        CATEGORIE_BLOQUANTE,
    }


def anomalie_necessite_traitement_rh(type_anomalie: str) -> bool:
    """Indique si l'anomalie doit apparaitre comme dossier RH a verifier."""
    return categorie_anomalie(type_anomalie) == CATEGORIE_RH


def _contexte_canonique(type_anomalie: str, contexte: Optional[dict]) -> dict:
    """Ajoute la classification sans ecraser les donnees existantes."""
    resultat = dict(contexte or {})
    categorie = categorie_anomalie(type_anomalie)
    resultat.setdefault('categorie', categorie)
    resultat.setdefault('bloquante', anomalie_est_bloquante(type_anomalie))
    resultat.setdefault('traitement_rh_requis', anomalie_necessite_traitement_rh(type_anomalie))
    return resultat


def enregistrer_anomalie(
    type_anomalie: str,
    message: str,
    employe: Optional[Employe] = None,
    matricule_scanne: str = '',
    site: Optional[Site] = None,
    date_pointage=None,
    contexte: Optional[dict] = None,
    pointage: Optional[Pointage] = None,
) -> AnomaliePointage:
    """Enregistre une anomalie de maniere atomique et coherent.

    ``pointage`` est facultatif. Le modele AnomaliePointage ne possede pas de
    relation directe vers Pointage ; son ID est donc conserve dans ``contexte``.

    Les erreurs de persistence ne sont pas avalees : si la base refuse
    l'enregistrement, l'appelant recoit l'exception au lieu d'un faux objet
    AnomaliePointage non sauvegarde.
    """
    contexte = _contexte_canonique(type_anomalie, contexte)

    if pointage is not None and getattr(pointage, 'pk', None) is not None:
        contexte.setdefault('pointage_id', pointage.pk)

    with transaction.atomic():
        if type_anomalie in DEDUP_TYPES:
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

            existante = (
                AnomaliePointage.objects
                .filter(**cle_lookup)
                .order_by('-created_at')
                .first()
            )
            if existante:
                contexte_existant = dict(existante.contexte or {})
                contexte_existant.update(contexte)
                contexte_existant['tentatives'] = contexte_existant.get('tentatives', 1) + 1
                contexte_existant['derniere_tentative'] = timezone.now().isoformat()
                if site:
                    contexte_existant['dernier_site_tente'] = site.nom
                existante.contexte = contexte_existant
                existante.save(update_fields=['contexte'])
                logger.info(
                    '[enregistrer_anomalie] %s deja ouverte (id=%s) - tentative supplementaire tracee',
                    type_anomalie,
                    existante.id,
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
            '[enregistrer_anomalie] %s creee (id=%s) categorie=%s emp=%s',
            type_anomalie,
            anomalie.id,
            contexte['categorie'],
            employe.id if employe else matricule_scanne,
        )
        return anomalie


def marquer_traitee(
    anomalie: AnomaliePointage,
    administrateur: CustomUser,
    commentaire: str = '',
    corrections: Optional[list] = None,
    pointage_concerne: Optional[Pointage] = None,
    type_action: str = 'correction',
) -> AnomalieTraitement:
    """Passe une anomalie ouverte a l'etat traitee, une seule fois."""
    if not administrateur.is_staff:
        raise PermissionError('Seul un administrateur ou RH peut traiter une anomalie.')

    commentaire = (commentaire or '').strip()
    if not commentaire:
        raise ValueError('Un commentaire est obligatoire pour traiter une anomalie.')

    valides = {choice for choice, _ in AnomalieTraitement.TYPE_ACTION_CHOICES}
    if type_action not in valides:
        raise ValueError(f'type_action invalide : {type_action!r}')

    with transaction.atomic():
        anomalie_db = AnomaliePointage.objects.select_for_update().get(pk=anomalie.pk)
        if anomalie_db.statut == AnomaliePointage.STATUT_CLOTUREE:
            raise ValueError('Impossible de retraiter une anomalie deja cloturee.')
        if anomalie_db.statut != AnomaliePointage.STATUT_OUVERTE:
            raise ValueError('Cette anomalie a deja ete traitee et ne peut plus etre remplacee.')

        pointage_db = None
        if pointage_concerne and pointage_concerne.pk:
            pointage_db = Pointage.objects.select_for_update().get(pk=pointage_concerne.pk)

        traitement = AnomalieTraitement.objects.create(
            anomalie=anomalie_db,
            administrateur=administrateur,
            commentaire=commentaire,
            corrections=corrections or [],
            pointage_concerne=pointage_db,
            type_action=type_action,
        )
        anomalie_db.statut = AnomaliePointage.STATUT_TRAITEE
        anomalie_db.save(update_fields=['statut'])

    logger.info(
        '[marquer_traitee] anomalie=%s traitee (%s) par %s (%s correction(s))',
        anomalie.pk,
        type_action,
        administrateur,
        len(corrections or []),
    )
    return traitement


def marquer_cloturee(anomalie: AnomaliePointage, administrateur: CustomUser) -> AnomaliePointage:
    """Cloture une anomalie deja traitee, de maniere atomique."""
    if not administrateur.is_staff:
        raise PermissionError('Seul un administrateur ou RH peut cloturer une anomalie.')

    with transaction.atomic():
        anomalie_db = AnomaliePointage.objects.select_for_update().get(pk=anomalie.pk)

        if anomalie_db.statut == AnomaliePointage.STATUT_OUVERTE:
            raise ValueError("Impossible de cloturer une anomalie qui n'a pas ete traitee.")
        if anomalie_db.statut == AnomaliePointage.STATUT_CLOTUREE:
            return anomalie_db

        anomalie_db.statut = AnomaliePointage.STATUT_CLOTUREE
        anomalie_db.cloturee_par = administrateur
        anomalie_db.date_cloture = timezone.now()
        anomalie_db.save(update_fields=['statut', 'cloturee_par', 'date_cloture'])

    logger.info('[marquer_cloturee] anomalie=%s cloturee par %s', anomalie.pk, administrateur)
    return anomalie_db


def compter_anomalies_ouvertes() -> int:
    """Nombre d'anomalies ouvertes, utilise par les badges du dashboard."""
    return AnomaliePointage.objects.filter(statut=AnomaliePointage.STATUT_OUVERTE).count()
