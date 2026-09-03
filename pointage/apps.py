from django.apps import AppConfig


class PointageConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pointage'

    def ready(self):
        import pointage.signals  # noqa: F401 — enregistre les @receiver définis dans signals.py
        # Charge les garde-fous au démarrage : ils complètent les permissions
        # et empêchent les raccourcis métier hors des flux officiels.
        import pointage.admin_hardening  # noqa: F401
        import pointage.overtime_admin  # noqa: F401
        import pointage.api_integrity  # noqa: F401
        import pointage.model_integrity  # noqa: F401
        import pointage.mobile_integrity  # noqa: F401
        import pointage.web_integrity  # noqa: F401
        import pointage.web_scan_integrity  # noqa: F401
        import pointage.timestamp_integrity  # noqa: F401
