# pointage/context_processors.py

from django.utils import timezone
from datetime import timedelta
from django.contrib.admin.models import LogEntry
from .models import Employe, Pointage, AnomaliePointage
from .anomalies import compter_anomalies_ouvertes


def dashboard_context(request):
    """Fournit les données statistiques pour le dashboard Jazzmin."""
    
    today = timezone.localtime(timezone.now()).date()
    
    # Statistiques principales
    total_employes = Employe.objects.filter(actif=True).count()
    
    today_pointages = Pointage.objects.filter(date_pointage=today)
    presents_aujourdhui = today_pointages.values('employe').distinct().count()
    
    gardes_en_cours = Pointage.objects.filter(
        date_pointage=today, periode='nuit',
        type_journee='garde', heure_depart__isnull=True
    ).count()
    
    anomalies_ouvertes = compter_anomalies_ouvertes()
    
    # Données hebdomadaires pour le graphique
    days = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
    weekly_presents = []
    weekly_absents = []
    weekly_retards = []
    
    for i in range(6, -1, -1):
        jour = today - timedelta(days=i)
        pointages_jour = Pointage.objects.filter(date_pointage=jour)
        
        presents = pointages_jour.values('employe').distinct().count()
        retards = pointages_jour.filter(
            periode__in=['matin', 'apres_midi'], retard__gt=timedelta(0)
        ).count()
        
        weekly_presents.append(presents)
        weekly_absents.append(total_employes - presents)
        weekly_retards.append(retards)
    
    # Logs récents
    logs_recents = LogEntry.objects.select_related(
        'user', 'content_type'
    ).order_by('-action_time')[:10]
    
    # Anomalies récentes
    anomalies_recentes = AnomaliePointage.objects.select_related(
        'employe', 'site'
    ).order_by('-created_at')[:10]
    
    return {
        'total_employes': total_employes,
        'presents_aujourdhui': presents_aujourdhui,
        'gardes_en_cours': gardes_en_cours,
        'anomalies_ouvertes': anomalies_ouvertes,
        'weekly_labels': days,
        'weekly_presents': weekly_presents,
        'weekly_absents': weekly_absents,
        'weekly_retards': weekly_retards,
        'logs_recents': logs_recents,
        'anomalies_recentes': anomalies_recentes,
    }