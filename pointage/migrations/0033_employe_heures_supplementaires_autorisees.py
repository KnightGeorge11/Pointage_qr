from django.db import migrations, models


def autoriser_employes_existants(apps, schema_editor):
    Employe = apps.get_model('pointage', 'Employe')
    # Préserve le comportement historique des employés déjà présents.
    Employe.objects.all().update(heures_supplementaires_autorisees=True)


class Migration(migrations.Migration):

    dependencies = [
        ('pointage', '0032_configuration_duree_journee'),
    ]

    operations = [
        migrations.AddField(
            model_name='employe',
            name='heures_supplementaires_autorisees',
            field=models.BooleanField(
                default=False,
                help_text='Autorise cet employé à effectuer des heures supplémentaires. La validation de chaque pointage reste gérée séparément par la RH.',
                verbose_name='Heures supplémentaires autorisées',
            ),
        ),
        migrations.RunPython(
            autoriser_employes_existants,
            migrations.RunPython.noop,
        ),
    ]
