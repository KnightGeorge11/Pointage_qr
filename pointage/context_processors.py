# pointage/context_processors.py

from django.utils import timezone
from datetime import timedelta
from django.contrib.admin.models import LogEntry
from django.db.models import Count, Q
from .models import Employe, Pointage, AnomaliePointage, Site, Poste
from .anomalies import compter_anomalies_ouvertes
from .models import DemandeModification, AnomaliePointage



def dashboard_context(request):
    """Fournit les données statistiques pour le dashboard Jazzmin."""
    
    print("🔴🔴🔴 dashboard_context EXÉCUTÉ 🔴🔴🔴")
    
    today = timezone.localtime(timezone.now()).date()
    
    # ============================================================
    # STATISTIQUES PRINCIPALES
    # ============================================================
    
    total_employes = Employe.objects.filter(actif=True).count()
    
    today_pointages = Pointage.objects.filter(date_pointage=today)
    presents_aujourdhui = today_pointages.values('employe').distinct().count()
    
    retards_aujourdhui = today_pointages.filter(
        periode__in=['matin', 'apres_midi'], 
        retard__gt=timedelta(0)
    ).count()
    
    absents_aujourdhui = total_employes - presents_aujourdhui
    
    gardes_en_cours = Pointage.objects.filter(
        date_pointage=today, 
        periode='nuit',
        type_journee='garde', 
        heure_depart__isnull=True
    ).count()
    
    anomalies_ouvertes = compter_anomalies_ouvertes()
    
    # ============================================================
    # DONNÉES HEBDOMADAIRES POUR LE GRAPHIQUE
    # ============================================================
    
    jours_labels = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
    weekly_presents = []
    weekly_absents = []
    weekly_retards = []
    
    # Calcul du lundi de la semaine en cours
    today_weekday = today.weekday()  # 0=Lundi, 6=Dimanche
    start_of_week = today - timedelta(days=today_weekday)
    
    for i in range(7):
        jour = start_of_week + timedelta(days=i)
        pointages_jour = Pointage.objects.filter(date_pointage=jour)
        
        presents = pointages_jour.values('employe').distinct().count()
        retards = pointages_jour.filter(
            periode__in=['matin', 'apres_midi'], 
            retard__gt=timedelta(0)
        ).count()
        
        weekly_presents.append(presents)
        weekly_absents.append(total_employes - presents)
        weekly_retards.append(retards)
    
    # ============================================================
    # DONNÉES D'ÉVOLUTION (4 semaines)
    # ============================================================
    
    evolution_labels = []
    evolution_presence = []
    evolution_ponctualite = []
    
    for i in range(3, -1, -1):
        week_start = start_of_week - timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        
        evolution_labels.append(f"Sem. {week_start.strftime('%d/%m')}")
        
        pointages_semaine = Pointage.objects.filter(
            date_pointage__gte=week_start,
            date_pointage__lte=week_end
        )
        
        employes_semaine = pointages_semaine.values('employe').distinct().count()
        if total_employes > 0:
            taux_presence = round((employes_semaine / total_employes) * 100, 1)
        else:
            taux_presence = 0.0
        
        pointages_sans_retard = pointages_semaine.filter(
            periode__in=['matin', 'apres_midi'],
            retard=timedelta(0)
        ).count()
        total_pointages = pointages_semaine.filter(
            periode__in=['matin', 'apres_midi']
        ).count()
        if total_pointages > 0:
            taux_ponctualite = round((pointages_sans_retard / total_pointages) * 100, 1)
        else:
            taux_ponctualite = 0.0
        
        evolution_presence.append(taux_presence)
        evolution_ponctualite.append(taux_ponctualite)
    
    # ============================================================
    # DONNÉES DES POSTES (camembert)
    # ============================================================
    
    postes_data = []
    postes_qs = Poste.objects.annotate(
        employes_count=Count('employes', filter=Q(employes__actif=True))
    ).filter(employes_count__gt=0)
    
    for poste in postes_qs:
        postes_data.append({
            'nom': poste.nom,
            'count': poste.employes_count,
            'couleur': poste.couleur or '#2563EB'
        })
    
    # ============================================================
    # HISTORIQUE DÉTAILLÉ DES ACTIVITÉS
    # ============================================================
    
    # Récupérer les logs d'administration
    logs_recents = LogEntry.objects.select_related(
        'user', 'content_type'
    ).order_by('-action_time')[:20]
    
    # Enrichir les logs avec des informations supplémentaires
    logs_detailed = []
    for log in logs_recents:
        log_data = {
            'id': log.id,
            'user': log.user,
            'action_time': log.action_time,
            'action_flag': log.action_flag,
            'action_display': log.get_action_flag_display(),
            'content_type': log.content_type,
            'object_repr': log.object_repr,
            'object_id': log.object_id,
            'change_message': log.change_message,
            'is_addition': log.action_flag == 1,
            'is_change': log.action_flag == 2,
            'is_deletion': log.action_flag == 3,
        }
        logs_detailed.append(log_data)
    
    # ============================================================
    # DERNIERS POINTAGES
    # ============================================================
    
    pointages_recents = Pointage.objects.select_related(
        'employe', 'site'
    ).order_by('-date_creation')[:10]
    
    pointages_data = []
    for p in pointages_recents:
        pointages_data.append({
            'id': p.id,
            'employe': p.employe.get_nom_complet(),
            'matricule': p.employe.matricule,
            'date': p.date_pointage,
            'periode': p.get_periode_display(),
            'heure_arrivee': p.heure_arrivee.strftime('%H:%M') if p.heure_arrivee else '—',
            'heure_depart': p.heure_depart.strftime('%H:%M') if p.heure_depart else '—',
            'site': p.site.nom if p.site else '—',
            'statut': p.statut,
            'statut_display': p.get_statut_display(),
            'retard': p.get_retard_minutes() if p.retard else 0,
        })
    
    # ============================================================
    # ANOMALIES RÉCENTES
    # ============================================================
    
    anomalies_recentes = AnomaliePointage.objects.select_related(
        'employe', 'site'
    ).order_by('-created_at')[:10]
    
    anomalies_data = []
    for a in anomalies_recentes:
        anomalies_data.append({
            'id': a.id,
            'type': a.type,
            'type_display': a.get_type_display(),
            'employe': a.employe.get_nom_complet() if a.employe else None,
            'matricule': a.employe.matricule if a.employe else a.matricule_scanne,
            'message': a.message,
            'created_at': a.created_at,
            'statut': a.statut,
            'statut_display': a.get_statut_display(),
            'gravite': a.gravite,
            'gravite_display': a.get_gravite_display(),
        })
    
    return {
        # Statistiques
        'total_employes': total_employes,
        'presents_aujourdhui': presents_aujourdhui,
        'absents_aujourdhui': absents_aujourdhui,
        'retards_aujourdhui': retards_aujourdhui,
        'gardes_en_cours': gardes_en_cours,
        'anomalies_ouvertes': anomalies_ouvertes,
        
        # Graphique hebdomadaire
        'weekly_labels': jours_labels,
        'weekly_presents': weekly_presents,
        'weekly_absents': weekly_absents,
        'weekly_retards': weekly_retards,
        
        # Graphique d'évolution
        'evolution_labels': evolution_labels,
        'evolution_presence': evolution_presence,
        'evolution_ponctualite': evolution_ponctualite,
        
        # Camembert des postes
        'postes_data': postes_data,
        
        # Logs détaillés
        'logs_detailed': logs_detailed,
        'logs_recents': logs_recents,
        
        # Pointages récents
        'pointages_data': pointages_data,
        'pointages_recents': pointages_recents,
        
        # Anomalies récentes
        'anomalies_data': anomalies_data,
        'anomalies_recentes': anomalies_recentes,
    }
 
def admin_badge_counts(request):
    """
    Fournit les compteurs pour les badges de la sidebar Jazzmin.
    Ces compteurs sont utilisés par la navigation personnalisée.
    """
    # Demandes en attente
    demandes_attente = DemandeModification.objects.filter(statut='en_attente').count()
    
    # Anomalies ouvertes
    anomalies_ouvertes = AnomaliePointage.objects.filter(
        statut=AnomaliePointage.STATUT_OUVERTE
    ).count()
    
    return {
        'demandes_attente': demandes_attente if demandes_attente > 0 else None,
        'anomalies_ouvertes': anomalies_ouvertes if anomalies_ouvertes > 0 else None,
    }