from django.db import migrations


TRIGGER_NAME = "pointage_enforce_overtime_authorization"
FUNCTION_NAME = "pointage_enforce_overtime_authorization_fn"

FORWARD_SQL = f"""
-- Existing overtime values were calculated before the RH authorization
-- workflow existed. They must not remain payable/accountable by default.
UPDATE pointage_pointage
SET heures_supplementaires = INTERVAL '0 seconds'
WHERE COALESCE(heures_supplementaires_autorisees, FALSE) = FALSE;

CREATE OR REPLACE FUNCTION {FUNCTION_NAME}()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- The stored overtime field is the authoritative amount used by
    -- reports/exports. It is therefore impossible to persist overtime
    -- unless an RH user has explicitly authorized it.
    IF COALESCE(NEW.heures_supplementaires_autorisees, FALSE) = FALSE THEN
        NEW.heures_supplementaires := INTERVAL '0 seconds';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON pointage_pointage;

CREATE TRIGGER {TRIGGER_NAME}
BEFORE INSERT OR UPDATE ON pointage_pointage
FOR EACH ROW
EXECUTE FUNCTION {FUNCTION_NAME}();
"""

REVERSE_SQL = f"""
DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON pointage_pointage;
DROP FUNCTION IF EXISTS {FUNCTION_NAME}();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("pointage", "0019_pointage_audit_and_overtime_authorization"),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
    ]
