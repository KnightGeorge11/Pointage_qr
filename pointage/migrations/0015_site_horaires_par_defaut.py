from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pointage", "0014_freeze_heures_supplementaires"),
    ]

    operations = [
        migrations.AlterField(
            model_name="site",
            name="heure_ouverture_apres_midi",
            field=models.TimeField(default="13:00"),
        ),
        migrations.AlterField(
            model_name="site",
            name="heure_fermeture_apres_midi",
            field=models.TimeField(default="17:00"),
        ),
    ]
