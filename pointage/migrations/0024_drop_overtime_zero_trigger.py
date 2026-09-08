from django.db import migrations


TRIGGER_NAME = "pointage_enforce_overtime_authorization"
FUNCTION_NAME = "pointage_enforce_overtime_authorization_fn"

# Le trigger installé en 0020 forçait heures_supplementaires à 0 sur CHAQUE
# INSERT/UPDATE tant que heures_supplementaires_autorisees n'était pas True.
# Effet de bord non voulu : le calcul automatique centralisé dans
# Pointage.calculer_heures_supplementaires() (basé sur les horaires réels du
# site) était systématiquement écrasé à 0, y compris à la création du
# pointage — aucune heure supplémentaire n'était donc plus jamais visible,
# même pour une simple consultation RH avant autorisation.
#
# Le contrôle métier voulu ("seules les heures autorisées par un RH sont
# payables/exportables") reste appliqué correctement en aval, au niveau de
# l'export Excel (voir admin_hardening._sanitize_overtime_export, qui filtre
# déjà sur heures_supplementaires_autorisees). Le trigger DB était donc
# redondant avec ce filtre et, en plus, cassait la visibilité du calcul brut.
#
# Le reste du dispositif d'autorisation (champ heures_supplementaires_autorisees,
# révocation automatique en cas de modification des données du pointage dans
# model_integrity.py, audit dans overtime_admin.py) est conservé tel quel.
FORWARD_SQL = f"""
DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON pointage_pointage;
DROP FUNCTION IF EXISTS {FUNCTION_NAME}();
"""

REVERSE_SQL = f"""
CREATE OR REPLACE FUNCTION {FUNCTION_NAME}()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF COALESCE(NEW.heures_supplementaires_autorisees, FALSE) = FALSE THEN
        NEW.heures_supplementaires := INTERVAL '0 seconds';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER {TRIGGER_NAME}
BEFORE INSERT OR UPDATE ON pointage_pointage
FOR EACH ROW
EXECUTE FUNCTION {FUNCTION_NAME}();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("pointage", "0023_backfill_anomaly_classification"),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
    ]
