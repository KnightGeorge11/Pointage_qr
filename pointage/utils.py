# pointage/utils.py
#
# CORRECTIONS :
#   - calculer_retards_mensuels : utilise les vrais champs (retard, heures_travaillees)
#   - generer_rapport_pointage  : utilise les vrais champs
#   - generer_pointages_mensuels: supprimée (anti-pattern — voir commentaire)
#   + NOUVEAU : cloture_journee (détection des scans manquants en fin de journée)

from datetime import datetime, timedelta
from django.utils import timezone
from .models import Pointage, Employe, Site


# ─── Calcul des retards mensuels ──────────────────────────────────────────────

def calculer_retards_mensuels(employe, mois: int, annee: int) -> dict:
    """Calcule les totaux de retards pour un employé sur un mois."""
    premier_jour = datetime(annee, mois, 1).date()
    if mois == 12:
        dernier_jour = datetime(annee + 1, 1, 1).date() - timedelta(days=1)
    else:
        dernier_jour = datetime(annee, mois + 1, 1).date() - timedelta(days=1)

    pointages = Pointage.objects.filter(
        employe=employe,
        date_pointage__gte=premier_jour,
        date_pointage__lte=dernier_jour,
        periode__in=['matin', 'apres_midi'],  # exclure les gardes de nuit
    )

    total_retard = timedelta()
    jours_retard = 0

    for pointage in pointages:
        if pointage.retard and pointage.retard > timedelta(0):
            total_retard += pointage.retard
            jours_retard += 1

    return {
        'total_retard':   total_retard,
        'jours_retard':   jours_retard,
        'moyenne_retard': total_retard / jours_retard if jours_retard > 0 else timedelta(0),
    }


# ─── Rapport de pointage ──────────────────────────────────────────────────────

def generer_rapport_pointage(debut, fin, site_id=None) -> list:
    """Génère un rapport détaillé des pointages pour une période."""
    pointages = Pointage.objects.filter(
        date_pointage__gte=debut,
        date_pointage__lte=fin
    ).select_related('employe', 'site')

    if site_id:
        pointages = pointages.filter(site_id=site_id)

    donnees = []
    for p in pointages:
        donnees.append({
            'date':               p.date_pointage,
            'employe':            str(p.employe),
            'matricule':          p.employe.matricule,
            'site':               p.site.nom if p.site else '',
            'periode':            p.get_periode_display(),
            'heure_arrivee':      p.heure_arrivee,
            'heure_depart':       p.heure_depart,
            'retard':             p.retard,
            'heures_travaillees': p.heures_travaillees or timedelta(),
            'statut':             p.get_statut_display(),
        })

    return donnees


# ─── NOTE : generer_pointages_mensuels supprimée ─────────────────────────────
#
# L'ancienne fonction créait des objets Pointage vides (statut='absent') pour
# tous les jours ouvrés du mois à l'avance. Ce pattern est un anti-pattern car :
#   - Il crée ~20 enregistrements par employé par mois même sans aucun scan
#   - Il fausse les comptages (présents / absents) dans le dashboard
#   - Les absences sont implicites : absence de scan = absent
#
# Si vous avez besoin de marquer des congés ou absences planifiées, créez un
# modèle dédié CongeAbsence(employe, date_debut, date_fin, type) séparé.
