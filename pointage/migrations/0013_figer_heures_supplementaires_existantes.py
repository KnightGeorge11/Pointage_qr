from datetime import datetime, timedelta

from django.db import migrations


def figer_heures_supplementaires(apps, schema_editor):
    """
    Calcule et fige heures_supplementaires pour tous les Pointage
    'apres_midi' déjà en base, sinon ils resteraient à NULL jusqu'à leur
    prochain save() — pas de risque, get_heures_supplementaires() a un
    filet de sécurité qui recalculerait à la volée sinon, mais autant
    figer tout de suite l'historique existant plutôt que d'attendre.

    Réimplémente le calcul en pur Python (sans passer par les méthodes du
    modèle réel : les modèles historiques des migrations n'ont que les
    champs, jamais les méthodes custom) — logique identique à
    Pointage.calculer_heures_supplementaires().
    """
    Pointage = apps.get_model('pointage', 'Pointage')

    a_traiter = Pointage.objects.filter(
        periode='apres_midi',
        heure_depart__isnull=False,
        site__isnull=False,
    ).select_related('site')

    a_mettre_a_jour = []
    for pointage in a_traiter:
        site = pointage.site
        heure_fermeture = site.heure_fermeture_apres_midi
        if not heure_fermeture:
            pointage.heures_supplementaires = timedelta(0)
        else:
            depart_dt    = datetime.combine(pointage.date_pointage, pointage.heure_depart)
            fermeture_dt = datetime.combine(pointage.date_pointage, heure_fermeture)
            pointage.heures_supplementaires = max(depart_dt - fermeture_dt, timedelta(0))
        a_mettre_a_jour.append(pointage)

    if a_mettre_a_jour:
        Pointage.objects.bulk_update(a_mettre_a_jour, ['heures_supplementaires'], batch_size=500)

    # Tout le reste (matin, gardes, pointages sans site/sans sortie) reste
    # à NULL — get_heures_supplementaires() les traite comme 0, cohérent
    # avec la règle métier (jamais d'heure sup pour ces cas).


def revert_noop(apps, schema_editor):
    # Rien à annuler : remettre à NULL ne perdrait rien d'important
    # (le filet de sécurité de get_heures_supplementaires() recalcule à
    # la volée si NULL), donc pas la peine d'écrire une vraie migration
    # inverse ici.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('pointage', '0012_audit_2_ajout_champs_config'),
    ]

    operations = [
        migrations.RunPython(figer_heures_supplementaires, revert_noop),
    ]
