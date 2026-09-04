from django.db import migrations


CATEGORIE_SECURITE = 'securite'
CATEGORIE_BLOQUANTE = 'bloquante'
CATEGORIE_RH = 'rh'

SECURITE = {
    'invalid_qr',
    'employe_inactif',
    'site_invalide',
}

BLOQUANTES = {
    'duplicate_scan',
    'outside_hours',
    'during_break',
    'day_complete',
    'missing_morning_exit',
    'transition_impossible',
    'invalid_state',
    'hors_plage_globale',
    'garde_multiple_non_supportee',
}

RH = {
    'depart_anticipe',
}


def classify(type_anomalie):
    if type_anomalie in SECURITE:
        return CATEGORIE_SECURITE
    if type_anomalie in RH:
        return CATEGORIE_RH
    return CATEGORIE_BLOQUANTE


def backfill(apps, schema_editor):
    AnomaliePointage = apps.get_model('pointage', 'AnomaliePointage')

    for anomalie in AnomaliePointage.objects.all().iterator():
        contexte = dict(anomalie.contexte or {})
        categorie = classify(anomalie.type)
        contexte.setdefault('categorie', categorie)
        contexte.setdefault('bloquante', categorie != CATEGORIE_RH)
        contexte.setdefault('traitement_rh_requis', categorie == CATEGORIE_RH)
        anomalie.contexte = contexte
        anomalie.save(update_fields=['contexte'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('pointage', '0022_enforce_night_departure_date'),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
