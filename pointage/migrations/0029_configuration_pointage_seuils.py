from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pointage', '0028_configuration_pointage'),
    ]

    operations = [
        migrations.AddField(
            model_name='configurationpointage',
            name='tolerance_minutes_defaut',
            field=models.PositiveSmallIntegerField(
                default=30,
                help_text="Utilisée par les sites qui n'ont pas de tolérance spécifique.",
                verbose_name='Tolérance par défaut (minutes)',
            ),
        ),
        migrations.AddField(
            model_name='configurationpointage',
            name='seuil_depart_anticipe_minutes_defaut',
            field=models.PositiveSmallIntegerField(
                default=15,
                help_text="Utilisé par les sites qui n'ont pas de seuil spécifique.",
                verbose_name='Seuil départ anticipé par défaut (minutes)',
            ),
        ),
    ]
