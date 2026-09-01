from django.db import migrations


TRIGGER_NAME = "pointage_freeze_heures_supplementaires"
FUNCTION_NAME = "pointage_freeze_heures_supplementaires_fn"


FORWARD_SQL = f"""
CREATE OR REPLACE FUNCTION {FUNCTION_NAME}()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- Once an overtime value has been persisted, a later save that does
    -- not change the attendance event itself must not silently recompute
    -- the historical value from the site's current schedule.
    --
    -- Recalculation remains allowed when the business event itself is
    -- changed (departure/date/site/period), which is what an explicit RH
    -- correction does.
    IF OLD.heures_supplementaires IS NOT NULL
       AND NEW.heures_supplementaires IS DISTINCT FROM OLD.heures_supplementaires
       AND NEW.heure_depart IS NOT DISTINCT FROM OLD.heure_depart
       AND NEW.date_pointage IS NOT DISTINCT FROM OLD.date_pointage
       AND NEW.site_id IS NOT DISTINCT FROM OLD.site_id
       AND NEW.periode IS NOT DISTINCT FROM OLD.periode
    THEN
        NEW.heures_supplementaires := OLD.heures_supplementaires;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON pointage_pointage;

CREATE TRIGGER {TRIGGER_NAME}
BEFORE UPDATE ON pointage_pointage
FOR EACH ROW
EXECUTE FUNCTION {FUNCTION_NAME}();
"""

REVERSE_SQL = f"""
DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON pointage_pointage;
DROP FUNCTION IF EXISTS {FUNCTION_NAME}();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("pointage", "0013_figer_heures_supplementaires_existantes"),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
    ]
