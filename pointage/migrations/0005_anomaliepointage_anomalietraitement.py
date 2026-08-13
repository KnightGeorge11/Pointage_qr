# Phase 4 — Gestion des anomalies de pointage
#
# CORRECTIF (v2) : sur ce projet, CustomUser a été retiré de l'état de
# migration de l'app 'pointage' (cf. 0002_alerterh_...) et son état de
# migration se trouve sous 'auth.customuser' (migration auth/0013_customuser).
# Mais la TABLE PHYSIQUE réelle a ensuite été renommée manuellement en
# base ('auth_customuser' -> 'pointage_customuser'), sans mise à jour de
# l'état des migrations. Toute nouvelle contrainte FK créée par Django en
# se basant sur l'état ('auth_customuser') échoue donc, alors que les
# anciennes contraintes (créées avant le renommage) continuent de
# fonctionner car PostgreSQL les fait suivre automatiquement.
#
# Solution : db_constraint=False sur les deux FK vers l'utilisateur.
# La relation reste 100% fonctionnelle côté ORM/Python (jointures,
# related_name, etc.) ; seule la contrainte SQL physique est omise,
# ce qui évite de dépendre du nom de table exact.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pointage", "0004_pointage_date_depart"),
        ("auth", "0013_customuser"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnomaliePointage",
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
                    "type",
                    models.CharField(
                        choices=[
                            ("invalid_qr", "QR invalide"),
                            ("employe_inactif", "Employé inactif"),
                            ("site_invalide", "Site invalide"),
                            ("hors_plage_globale", "Hors plage horaire globale"),
                            ("duplicate_scan", "Double scan"),
                            ("outside_hours", "Hors horaires du site"),
                            ("during_break", "Scan pendant la pause"),
                            ("day_complete", "Journée déjà terminée"),
                            ("missing_morning_exit", "Sortie matin manquante"),
                            ("transition_impossible", "Transition impossible"),
                            ("invalid_state", "État invalide"),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "matricule_scanne",
                    models.CharField(
                        blank=True,
                        help_text=(
                            "Matricule brut du QR scanné, conservé même si "
                            "l'employé n'a pas pu être identifié."
                        ),
                        max_length=50,
                    ),
                ),
                (
                    "date_pointage",
                    models.DateField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "message",
                    models.TextField(),
                ),
                (
                    "contexte",
                    models.JSONField(
                        blank=True,
                        default=dict,
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("ouverte", "Ouverte"),
                            ("traitee", "Traitée"),
                            ("cloturee", "Clôturée"),
                        ],
                        default="ouverte",
                        max_length=10,
                    ),
                ),
                (
                    "date_cloture",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                    ),
                ),
                (
                    "cloturee_par",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="anomalies_cloturees",
                        to="auth.customuser",
                        db_constraint=False,
                    ),
                ),
                (
                    "employe",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="anomalies",
                        to="pointage.employe",
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="anomalies",
                        to="pointage.site",
                    ),
                ),
            ],
            options={
                "verbose_name": "Anomalie de pointage",
                "verbose_name_plural": "Anomalies de pointage",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="AnomalieTraitement",
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
                    "date_traitement",
                    models.DateTimeField(
                        auto_now_add=True,
                    ),
                ),
                (
                    "commentaire",
                    models.TextField(
                        blank=True,
                    ),
                ),
                (
                    "corrections",
                    models.JSONField(
                        blank=True,
                        default=list,
                    ),
                ),
                (
                    "administrateur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="anomalies_traitees",
                        to="auth.customuser",
                        db_constraint=False,
                    ),
                ),
                (
                    "anomalie",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="traitement",
                        to="pointage.anomaliepointage",
                    ),
                ),
                (
                    "pointage_concerne",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="corrections_anomalies",
                        to="pointage.pointage",
                    ),
                ),
            ],
            options={
                "verbose_name": "Traitement d'anomalie",
                "verbose_name_plural": "Traitements d'anomalies",
                "ordering": ["-date_traitement"],
            },
        ),
        migrations.AddIndex(
            model_name="anomaliepointage",
            index=models.Index(
                fields=["statut", "created_at"],
                name="pointage_an_statut_be7e15_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="anomaliepointage",
            index=models.Index(
                fields=["type", "created_at"],
                name="pointage_an_type_0221ac_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="anomaliepointage",
            index=models.Index(
                fields=["employe", "date_pointage"],
                name="pointage_an_employe_46e264_idx",
            ),
        ),
    ]
