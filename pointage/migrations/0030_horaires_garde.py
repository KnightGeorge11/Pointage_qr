from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pointage', '0029_configuration_pointage_seuils'),
    ]

    operations = [
        migrations.AddField(
            model_name='site',
            name='heure_debut_garde',
            field=models.TimeField(
                blank=True,
                help_text="Début de la plage de garde. Laisser vide pour utiliser la configuration globale.",
                null=True,
                verbose_name='Début de garde',
            ),
        ),
        migrations.AddField(
            model_name='site',
            name='heure_fin_garde',
            field=models.TimeField(
                blank=True,
                help_text="Fin de la plage de garde. Une fin plus tôt que le début signifie une garde traversant minuit.",
                null=True,
                verbose_name='Fin de garde',
            ),
        ),
        migrations.AddField(
            model_name='configurationpointage',
            name='heure_debut_garde',
            field=models.TimeField(
                default='20:00',
                help_text="Utilisée par les sites qui n'ont pas d'horaire de garde spécifique.",
                verbose_name='Début de garde par défaut',
            ),
        ),
        migrations.AddField(
            model_name='configurationpointage',
            name='heure_fin_garde',
            field=models.TimeField(
                default='06:00',
                help_text="Une fin plus tôt que le début signifie une garde traversant minuit.",
                verbose_name='Fin de garde par défaut',
            ),
        ),
    ]
