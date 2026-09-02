from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('pointage', '0016_pointage_integrity_checks'),
    ]

    operations = [
        migrations.AlterField(
            model_name='site',
            name='tolerance_minutes',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="Marge acceptée avant/après les horaires du site pour accepter un scan (ex : arriver 10 min avant l'ouverture reste accepté). Laisser vide pour utiliser la valeur par défaut du système (30 min).",
                null=True,
                verbose_name='Tolérance (minutes)',
            ),
        ),
    ]
