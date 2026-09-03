from django.db import migrations


SQL_FORWARD = """
ALTER TABLE pointage_pointage
    ADD CONSTRAINT pointage_departure_date_coherent
    CHECK (
        date_depart IS NULL
        OR date_depart = date_pointage
        OR (
            periode = 'nuit'
            AND date_depart = date_pointage + 1
        )
    ) NOT VALID;

ALTER TABLE pointage_pointage
    ADD CONSTRAINT pointage_night_departure_time_date_coherent
    CHECK (
        periode <> 'nuit'
        OR heure_depart IS NULL
        OR heure_arrivee IS NULL
        OR date_depart IS NULL
        OR (
            heure_depart >= heure_arrivee
            AND date_depart = date_pointage
        )
        OR (
            heure_depart < heure_arrivee
            AND date_depart = date_pointage + 1
        )
    ) NOT VALID;
"""

SQL_REVERSE = """
ALTER TABLE pointage_pointage
    DROP CONSTRAINT IF EXISTS pointage_night_departure_time_date_coherent;
ALTER TABLE pointage_pointage
    DROP CONSTRAINT IF EXISTS pointage_departure_date_coherent;
"""


class Migration(migrations.Migration):
    dependencies = [
        ('pointage', '0021_rename_pointage_po_pointag_5b5c2d_idx_pointage_po_pointag_feef60_idx_and_more'),
    ]

    operations = [
        migrations.RunSQL(SQL_FORWARD, SQL_REVERSE),
    ]
