from django.apps import AppConfig


class PointageConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pointage'

    def ready(self):
        import pointage.signals  # noqa: F401 — enregistre les @receiver définis dans signals.py
        # Charge l'admin avant les modules qui le patchent : Django peut appeler
        # ready() avant autodiscover, donc l'ordre est important ici.
        import pointage.admin_hardening  # noqa: F401 — verrouille l'administration RH et les traces immuables
        import pointage.overtime_admin  # noqa: F401 — ajoute les actions RH d'autorisation des heures supplémentaires
