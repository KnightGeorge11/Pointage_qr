# pointage/anomaly_correction.py
#
# Service unique de correction RH depuis une anomalie.
# Le workflow Web et l'API utilisent le même chemin afin d'éviter qu'une
# correction soit seulement enregistrée dans AnomalieTraitement sans modifier
# réellement le pointage.

from django.core.exceptions import ValidationError
from django.db import transaction

from .forms import PointageForm
from .models import AnomaliePointage, AnomalieTraitement, Pointage, PointageAudit
from .anomalies import marquer_traitee


POINTAGE_AUDIT_FIELDS = (
    'employe',
    'site',
    'date_pointage',
    'periode',
    'type_journee',
    'heure_arrivee',
    'heure_depart',
    'statut',
    'notes',
)


def _serialize_value(value):
    if value is None:
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


def snapshot_pointage(pointage):
    """Retourne un état JSON-safe des champs métier d'un pointage."""
    return {
        field: (
            getattr(pointage, f'{field}_id')
            if field in ('employe', 'site')
            else _serialize_value(getattr(pointage, field))
        )
        for field in POINTAGE_AUDIT_FIELDS
    }


@transaction.atomic
def corriger_pointage_anomalie(
    anomalie,
    administrateur,
    donnees,
    commentaire='',
):
    """Applique une correction RH réelle et trace son résultat.

    donnees contient les champs de PointageForm. Les champs employe/date/
    période peuvent être omis : dans ce cas, la cible de l'anomalie est
    utilisée. Une anomalie clôturée est définitivement immuable.

    Retourne (pointage, corrections, created).
    """
    anomalie = (
        AnomaliePointage.objects
        .select_for_update()
        .select_related('employe', 'site')
        .get(pk=anomalie.pk)
    )

    if anomalie.statut == AnomaliePointage.STATUT_CLOTUREE:
        raise ValueError("Cette anomalie est déjà clôturée.")

    data = dict(donnees or {})

    if not data.get('employe') and anomalie.employe_id:
        data['employe'] = anomalie.employe_id
    if not data.get('site') and anomalie.site_id:
        data['site'] = anomalie.site_id
    if not data.get('date_pointage') and anomalie.date_pointage:
        data['date_pointage'] = anomalie.date_pointage

    contexte = anomalie.contexte or {}
    if not data.get('periode') and contexte.get('periode'):
        data['periode'] = contexte['periode']

    employe_id = data.get('employe')
    date_pointage = data.get('date_pointage')
    periode = data.get('periode')

    if not employe_id or not date_pointage or not periode:
        raise ValidationError(
            "Employé, date et période sont obligatoires pour corriger un pointage."
        )

    pointage_existant = (
        Pointage.objects
        .select_for_update()
        .filter(
            employe_id=employe_id,
            date_pointage=date_pointage,
            periode=periode,
        )
        .first()
    )

    before = snapshot_pointage(pointage_existant) if pointage_existant else {}

    form = PointageForm(data=data, instance=pointage_existant)
    if not form.is_valid():
        raise ValidationError(form.errors)

    pointage = form.save()
    pointage.refresh_from_db()

    after = snapshot_pointage(pointage)
    corrections = []
    if pointage_existant:
        for champ in POINTAGE_AUDIT_FIELDS:
            if before.get(champ) != after.get(champ):
                corrections.append({
                    'champ': champ,
                    'ancienne_valeur': before.get(champ),
                    'nouvelle_valeur': after.get(champ),
                })

    PointageAudit.objects.create(
        pointage=pointage,
        administrateur=administrateur,
        action=(
            PointageAudit.ACTION_UPDATE
            if pointage_existant
            else PointageAudit.ACTION_CREATE
        ),
        avant=before,
        apres=after,
        motif=commentaire or f"Correction de l'anomalie #{anomalie.pk}.",
    )

    marquer_traitee(
        anomalie,
        administrateur,
        type_action=AnomalieTraitement.ACTION_CORRECTION,
        commentaire=commentaire,
        corrections=corrections,
        pointage_concerne=pointage,
    )

    return pointage, corrections, pointage_existant is None
