"""Corrections métier pour les statistiques de présence.

Un Pointage de garde peut exister avant le scan comme réservation de garde
(heure_arrivee=NULL). Une réservation n'est pas une présence et ne doit donc
jamais alimenter les compteurs de présence, d'absence inverse ou de ponctualité.
"""

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from .models import Employe, Pointage, Poste, DemandeModification
from .anomalies import compter_anomalies_ouvertes


def _presence_qs(qs):
    """Ne compter que les pointages ayant une véritable heure d'arrivée."""
    return qs.filter(heure_arrivee__isnull=False)


@login_required
def dashboard(request):
    today = timezone.localtime(timezone.now()).date()
    total_employes = Employe.objects.filter(actif=True).count()

    today_pointages = Pointage.objects.filter(date_pointage=today)
    presence_today = _presence_qs(today_pointages)
    presents_aujourdhui = presence_today.values('employe').distinct().count()
    retards = presence_today.filter(
        periode__in=['matin', 'apres_midi'], retard__gt=timedelta(0)
    ).count()
    gardes_en_cours = Pointage.objects.filter(
        periode='nuit', type_journee='garde', heure_arrivee__isnull=False,
        heure_depart__isnull=True,
        date_pointage__gte=today - timedelta(days=1),
        date_pointage__lte=today,
    ).count()

    pointages_recents = today_pointages.select_related('employe', 'site').order_by('-date_creation')[:10]
    demandes_en_attente = DemandeModification.objects.filter(statut='en_attente').count()
    anomalies_ouvertes = compter_anomalies_ouvertes()

    week_ago = today - timedelta(days=6)
    daily_stats = _presence_qs(Pointage.objects.filter(
        date_pointage__gte=week_ago, date_pointage__lte=today
    )).values('date_pointage').annotate(
        presents=Count('employe', distinct=True),
        retards=Count('id', filter=Q(periode__in=['matin', 'apres_midi'], retard__gt=timedelta(0)))
    )
    stats_by_date = {s['date_pointage']: s for s in daily_stats}

    jours_labels, jours_presents, jours_absents, jours_retards = [], [], [], []
    for i in range(6, -1, -1):
        jour = today - timedelta(days=i)
        jours_labels.append(jour.strftime('%a'))
        s = stats_by_date.get(jour, {})
        p = s.get('presents', 0)
        r = s.get('retards', 0)
        jours_presents.append(p)
        jours_absents.append(max(0, total_employes - p))
        jours_retards.append(r)

    four_weeks_ago = today - timedelta(days=today.weekday() + 21)
    all_weekly = _presence_qs(Pointage.objects.filter(
        date_pointage__gte=four_weeks_ago, date_pointage__lte=today
    ))

    semaines_labels, semaines_taux_presence, semaines_taux_punctualite = [], [], []
    for i in range(3, -1, -1):
        start_of_week = today - timedelta(days=today.weekday() + 7*i)
        end_of_week = start_of_week + timedelta(days=6)
        semaines_labels.append(f"Sem. {start_of_week.strftime('%d/%m')}")
        semaine_qs = all_weekly.filter(date_pointage__gte=start_of_week, date_pointage__lte=end_of_week)
        employes_semaine = semaine_qs.values('employe').distinct().count()
        taux_presence = (employes_semaine / total_employes * 100) if total_employes else 0
        pointages_sans_ret = semaine_qs.filter(
            periode__in=['matin', 'apres_midi'], retard=timedelta(0)
        ).count()
        total_pointages = semaine_qs.filter(periode__in=['matin', 'apres_midi']).count()
        taux_punctualite = (pointages_sans_ret / total_pointages * 100) if total_pointages else 0
        semaines_taux_presence.append(round(taux_presence, 1))
        semaines_taux_punctualite.append(round(taux_punctualite, 1))

    postes_qs = Poste.objects.annotate(
        employes_count=Count('employes', filter=Q(employes__actif=True))
    ).filter(employes_count__gt=0)
    postes_stats = [{'nom': p.nom, 'count': p.employes_count, 'couleur': p.couleur} for p in postes_qs]

    context = {
        'total_employes': total_employes,
        'presents_aujourdhui': presents_aujourdhui,
        'absents_aujourdhui': max(0, total_employes - presents_aujourdhui),
        'retards_aujourdhui': retards,
        'gardes_en_cours': gardes_en_cours,
        'pointages_recents': pointages_recents,
        'demandes_en_attente': demandes_en_attente,
        'anomalies_ouvertes': anomalies_ouvertes,
        'aujourdhui': today,
        'daily_data': {
            'presents': presents_aujourdhui,
            'absents': max(0, total_employes - presents_aujourdhui),
            'retards': retards,
            'gardes': gardes_en_cours,
        },
        'weekly_data': {
            'labels': jours_labels,
            'presents': jours_presents,
            'absents': jours_absents,
            'retards': jours_retards,
        },
        'evolution_data': {
            'labels': semaines_labels,
            'taux_presence': semaines_taux_presence,
            'taux_punctualite': semaines_taux_punctualite,
        },
        'postes_data': postes_stats,
    }
    return render(request, 'pointage/dashboard.html', context)


@login_required
def index(request):
    today = timezone.localtime(timezone.now()).date()
    pointages_aujourdhui = Pointage.objects.filter(date_pointage=today)
    total_employes = Employe.objects.filter(actif=True).count()
    presents_aujourdhui = _presence_qs(pointages_aujourdhui).values('employe').distinct().count()
    retards = _presence_qs(pointages_aujourdhui).filter(
        periode__in=['matin', 'apres_midi'], retard__gt=timedelta(0)
    )
    pointages_recents = pointages_aujourdhui.select_related('employe', 'site').order_by('-date_creation')[:10]
    context = {
        'total_employes': total_employes,
        'presents_aujourdhui': presents_aujourdhui,
        'absents_aujourdhui': max(0, total_employes - presents_aujourdhui),
        'retards_aujourdhui': retards.count(),
        'pointages_recents': pointages_recents,
        'aujourdhui': today,
    }
    return render(request, 'pointage/index.html', context)
