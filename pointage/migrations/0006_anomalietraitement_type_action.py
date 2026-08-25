# Phase 4.1 — Traitement RH structuré (Corriger / Justifier / Rejeter)
#
# Migration purement additive : un seul champ CharField (avec choices),
# blank=True, default='' pour ne rien casser sur les AnomalieTraitement
# déjà existants (ils garderont type_action='', affiché comme "Non
# spécifié" côté template).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pointage", "0005_anomaliepointage_anomalietraitement"),
    ]

    operations = [
        migrations.AddField(
            model_name="anomalietraitement",
            name="type_action",
            field=models.CharField(
                blank=True,
                choices=[
                    ("correction", "Correction du pointage"),
                    ("justification", "Justification (pointage inchangé)"),
                    ("rejet", "Rejet (pointage inchangé)"),
                ],
                default="",
                help_text=(
                    "Décision prise par l'Admin/RH. Vide pour les traitements "
                    "enregistrés avant l'introduction de ce champ."
                ),
                max_length=20,
            ),
        ),
    ]
