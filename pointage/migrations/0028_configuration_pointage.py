from django.db import migrations, models
import datetime


def create_default_configuration(apps, schema_editor):
    ConfigurationPointage = apps.get_model("pointage", "ConfigurationPointage")
    ConfigurationPointage.objects.get_or_create(
        pk=1,
        defaults={
            "heure_debut_systeme": datetime.time(5, 0),
            "heure_fin_systeme": datetime.time(23, 0),
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("pointage", "0027_jourferie"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfigurationPointage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "heure_debut_systeme",
                    models.TimeField(
                        default=datetime.time(5, 0),
                        help_text="Aucun scan normal n'est accepté avant cette heure.",
                        verbose_name="Début de la plage système",
                    ),
                ),
                (
                    "heure_fin_systeme",
                    models.TimeField(
                        default=datetime.time(23, 0),
                        help_text="Aucun scan normal n'est accepté après cette heure.",
                        verbose_name="Fin de la plage système",
                    ),
                ),
            ],
            options={
                "verbose_name": "Configuration du pointage",
                "verbose_name_plural": "Configuration du pointage",
            },
        ),
        migrations.RunPython(
            create_default_configuration,
            migrations.RunPython.noop,
        ),
    ]
