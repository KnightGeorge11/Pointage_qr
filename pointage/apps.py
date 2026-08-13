from django.apps import AppConfig

class PointageConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pointage'
    
    def ready(self):
        import pointage.signals
        from .models import CustomUser
        CustomUser._meta.app_label = 'auth'