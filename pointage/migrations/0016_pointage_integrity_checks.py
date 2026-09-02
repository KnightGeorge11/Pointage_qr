from django.db import migrations


SQL_CHECKS = """
ALTER TABLE pointage_pointage
    ADD CONSTRAINT pointage_normal_departure_after_arrival
    CHECK (
        periode = 'nuit'
        OR heure_arrivee IS NULL
        OR heure_depart IS NULL
        OR heure_depart >= heure_arrivee
    ) NOT VALID;

ALTER TABLE pointage_pointage
    ADD CONSTRAINT pointage_garde_only_night
    CHECK (
        type_journee <> 'garde'
        OR periode = 'nuit'
    ) NOT VALID;

ALTER TABLE pointage_pointage
    ADD CONSTRAINT pointage_night_only_garde_or_normal
    CHECK (
        periode <> 'nuit'
        OR type_journee IN ('garde', 'normal')
    ) NOT VALID;
"""

SQL_REVERSE = """
ALTER TABLE pointage_pointage
    DROP CONSTRAINT IF EXISTS pointage_normal_departure_after_arrival;
ALTER TABLE pointage_pointage
    DROP CONSTRAINT IF EXISTS pointage_garde_only_night;
ALTER TABLE pointage_pointage
    DROP CONSTRAINT IF EXISTS pointage_night_only_garde_or_normal;
"""


class Migration(migrations.Migration):
    dependencies = [
        ('pointage', '0015_site_horaires_par_defaut'),
    ]

    operations = [
        migrations.RunSQL(SQL_CHECKS, SQL_REVERSE),
    ]
