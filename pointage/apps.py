from django.apps import AppConfig


class PointageConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pointage'

    def ready(self):
        import pointage.signals  # noqa: F401 — enregistre les @receiver définis dans signals.py
        import pointage.overtime_admin  # noqa: F401 — ajoute les actions RH d'autorisation des heures supplémentaires
