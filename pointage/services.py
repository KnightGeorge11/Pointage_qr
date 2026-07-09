# pointage/services.py
#
# SERVICE CENTRAL DE POINTAGE
# Toutes les vues (web, API, mobile) appellent process_scan().
# Un seul endroit à maintenir et à tester.

from datetime import datetime, time, timedelta
from django.utils import timezone
from django.db import transaction

from .models import Employe, Site, Pointage, Scan, AlerteRH


# ─── Constantes ──────────────────────────────────────────────────────────────

SEUIL_DOUBLON_SECONDES = 120          # 2 minutes entre deux scans identiques
SEUIL_MIDI = time(12, 30)             # Avant → matin, après → après-midi (premier scan du jour)
PLAGE_MIN = time(5, 0)                # Heure minimale autorisée
PLAGE_MAX = time(23, 0)               # Heure maximale autorisée

NORMAL_SCAN_STEPS = [
    ('matin',      'heure_arrivee', 'entree_matin'),
    ('matin',      'heure_depart',  'sortie_matin'),
    ('apres_midi', 'heure_arrivee', 'entree_apres_midi'),
    ('apres_midi', 'heure_depart',  'sortie_apres_midi'),
]


# ─── Fonction principale ──────────────────────────────────────────────────────

def process_scan(matricule: str, qr_token: str, site_id: int,
                 mode: str = 'auto', force_sortie: bool = False,
                 confirmer_autorisation: bool = False,
                 force_new_garde: bool = False) -> dict:
    """
    Point d'entrée unique pour tout scan QR.

    Paramètres
    ----------
    matricule              : str   — extrait du QR code
    qr_token               : str   — UUID extrait du QR code, obligatoire
    site_id                : int   — ID du site de scan
    mode                   : str   — 'auto' (détection auto), 'garde' (nuit)
    force_sortie           : bool  — True = forcer la sortie même si anticipée
    confirmer_autorisation : bool  — True = l'agent confirme l'autorisation de sortie
    force_new_garde        : bool  — True = démarrer nouvelle garde même si une est en cours

    Retour
    ------
    dict avec les clés : status ('success'|'warning'|'error'|'confirm_required'),
                         code, message, data
    """

    now = timezone.localtime(timezone.now())

    # 1. Valider l'employé ET le token UUID (sécurité anti-fraude)
    try:
        employe = Employe.objects.get(
            matricule=matricule,
            qr_code_token=qr_token,   # ← vérification UUID obligatoire
            actif=True
        )
    except Employe.DoesNotExist:
        AlerteRH.objects.create(
            type='QR_INVALIDE',
            detail=f"Scan avec matricule={matricule} token={qr_token} — inconnu ou inactif",
            timestamp=now
        )
        return {
            'status': 'error',
            'code': 'QR_INVALIDE',
            'message': 'QR code invalide ou employé inactif.'
        }

    # 2. Valider le site
    try:
        site = Site.objects.get(id=site_id)
    except Site.DoesNotExist:
        return {
            'status': 'error',
            'code': 'SITE_INVALIDE',
            'message': f"Site {site_id} introuvable."
        }

    # 3. Vérifier que l'employé est affecté à ce site
    if not employe.sites.filter(id=site_id).exists():
        AlerteRH.objects.create(
            employe=employe,
            type='SITE_NON_AUTORISE',
            detail=f"Tentative de scan sur site {site.nom} non affecté à {employe.get_nom_complet()}",
            timestamp=now
        )
        return {
            'status': 'error',
            'code': 'SITE_NON_AUTORISE',
            'message': f"Vous n'êtes pas affecté au site « {site.nom} »."
        }

    # 4. Vérifier la plage horaire autorisée
    if not (PLAGE_MIN <= now.time() <= PLAGE_MAX):
        AlerteRH.objects.create(
            employe=employe,
            type='HORS_PLAGE',
            detail=f"Scan à {now.strftime('%H:%M')} en dehors de la plage {PLAGE_MIN}–{PLAGE_MAX}",
            timestamp=now
        )
        return {
            'status': 'warning',
            'code': 'HORS_PLAGE',
            'message': f"Scan en dehors des heures autorisées ({PLAGE_MIN.strftime('%Hh%M')}–{PLAGE_MAX.strftime('%Hh%M')})."
        }

    # 5. Anti-doublon temporel (protection contre double-scan accidentel)
    # Ignoré si force_sortie=True : la confirmation de sortie anticipée
    # est un 2e appel légitime qui ne doit pas être bloqué.
    if not force_sortie:
        dernier_scan = Scan.objects.filter(
            employe=employe,
            timestamp__gte=now - timedelta(seconds=SEUIL_DOUBLON_SECONDES)
        ).order_by('-timestamp').first()

        if dernier_scan:
            elapsed = (now - dernier_scan.timestamp).total_seconds()
            restant = max(1, int(SEUIL_DOUBLON_SECONDES - elapsed))
            return {
                'status': 'warning',
                'code': 'DOUBLON',
                'message': f"QR déjà scanné. Réessayez dans {restant} seconde(s)."
            }

    # 6. Router vers la logique garde ou normale
    with transaction.atomic():
        if mode == 'garde':
            return _process_garde(employe, site, now, force_new=force_new_garde)
        else:
            return _process_normal(employe, site, now,
                                   force_sortie=force_sortie,
                                   confirmer_autorisation=confirmer_autorisation)


# ─── Logique gardes de nuit ───────────────────────────────────────────────────

def _process_garde(employe, site, now, force_new=False):
    date_courante = now.date()
    heure = now.time()

    # Garde en cours → fin de garde (sauf si force_new demande une nouvelle garde)
    garde_en_cours = None
    if not force_new:
        garde_en_cours = Pointage.objects.select_for_update().filter(
            employe=employe,
            periode='nuit',
            type_journee='garde',
            heure_depart__isnull=True
        ).order_by('-date_pointage').first()

    if garde_en_cours:
        garde_en_cours.heure_depart = heure
        garde_en_cours.save()
        scan = Scan.objects.create(
            employe=employe, site=site,
            timestamp=now, type_scan='fin_garde',
            pointage=garde_en_cours
        )
        return {
            'status': 'success',
            'code': 'fin_garde',
            'message': f"Fin de garde enregistrée à {heure.strftime('%H:%M')}",
            'data': _build_response_data(scan, garde_en_cours, now)
        }

    # Garde planifiée → début de garde
    garde_planifiee = Pointage.objects.select_for_update().filter(
        employe=employe,
        date_pointage=date_courante,
        periode='nuit',
        type_journee='garde',
        heure_arrivee__isnull=True
    ).first()

    if garde_planifiee:
        garde_planifiee.heure_arrivee = heure
        garde_planifiee.site = site
        garde_planifiee.save()
        scan = Scan.objects.create(
            employe=employe, site=site,
            timestamp=now, type_scan='debut_garde',
            pointage=garde_planifiee
        )
        return {
            'status': 'success',
            'code': 'debut_garde',
            'message': f"Début de garde enregistré à {heure.strftime('%H:%M')}",
            'data': _build_response_data(scan, garde_planifiee, now)
        }

    # Nouvelle garde spontanée
    pointage = Pointage.objects.create(
        employe=employe, site=site,
        date_pointage=date_courante,
        periode='nuit', type_journee='garde',
        heure_arrivee=heure, statut='present'
    )
    scan = Scan.objects.create(
        employe=employe, site=site,
        timestamp=now, type_scan='debut_garde',
        pointage=pointage
    )
    return {
        'status': 'success',
        'code': 'debut_garde',
        'message': f"Début de garde enregistré à {heure.strftime('%H:%M')}",
        'data': _build_response_data(scan, pointage, now)
    }


# ─── Logique pointages normaux (E1 → S1 → E2 → S2) ──────────────────────────

def _process_normal(employe, site, now, force_sortie=False, confirmer_autorisation=False):
    date_courante = now.date()
    heure = now.time()
    return _process_normal_state_machine(
        employe=employe,
        site=site,
        now=now,
        date_courante=date_courante,
        heure=heure,
        force_sortie=force_sortie,
        confirmer_autorisation=confirmer_autorisation,
    )


# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_next_normal_scan_state(employe, date_courante, lock=False) -> dict | None:
    """
    Retourne la prochaine etape de pointage normal selon l'ordre obligatoire :
    entree matin -> sortie matin -> entree apres-midi -> sortie apres-midi.

    L'heure courante n'intervient jamais dans cette decision.
    """
    queryset = Pointage.objects
    if lock:
        queryset = queryset.select_for_update()

    pointages = {
        p.periode: p
        for p in queryset.filter(
            employe=employe,
            date_pointage=date_courante,
            periode__in=['matin', 'apres_midi'],
            type_journee='normal',
        )
    }

    for periode, champ, type_scan in NORMAL_SCAN_STEPS:
        pointage = pointages.get(periode)
        if not pointage or not getattr(pointage, champ):
            return {
                'periode': periode,
                'champ': champ,
                'type_scan': type_scan,
            }

    return None


def _process_normal_state_machine(
    employe,
    site,
    now,
    date_courante,
    heure,
    force_sortie=False,
    confirmer_autorisation=False,
):
    with transaction.atomic():
        prochain = get_next_normal_scan_state(employe, date_courante, lock=True)

        if not prochain:
            AlerteRH.objects.create(
                employe=employe,
                type='SCAN_EXCESS',
                detail=f"5e scan recu le {date_courante} - journee deja complete",
                timestamp=now
            )
            return {
                'status': 'warning',
                'code': 'JOURNEE_COMPLETE',
                'message': "Journee deja complete (4/4 scans enregistres)."
            }

        periode = prochain['periode']
        champ = prochain['champ']
        type_scan = prochain['type_scan']

        pointage, created = Pointage.objects.select_for_update().get_or_create(
            employe=employe,
            date_pointage=date_courante,
            periode=periode,
            defaults={'site': site, 'type_journee': 'normal'}
        )

        if not created and pointage.site != site:
            pointage.site = site

        if champ == 'heure_depart':
            _, heure_fermeture = site.get_horaires_pour_periode(periode) if site else (None, None)

            if heure_fermeture and heure < heure_fermeture and not force_sortie:
                from .models import AutorisationSortie
                autorisation = AutorisationSortie.get_ou_creer_du_mois(employe, date_courante)
                minutes_anticipation = int(
                    (datetime.combine(date_courante, heure_fermeture) -
                     datetime.combine(date_courante, heure)).total_seconds() / 60
                )
                return {
                    'status': 'confirm_required',
                    'code': 'SORTIE_ANTICIPEE',
                    'autorisation_disponible': autorisation.disponible,
                    'minutes_anticipation': minutes_anticipation,
                    'heure_fermeture_normale': heure_fermeture.strftime('%H:%M'),
                    'message': (
                        f"Sortie a {heure.strftime('%H:%M')} - "
                        f"{minutes_anticipation} min avant l'heure normale "
                        f"({heure_fermeture.strftime('%H:%M')}).\n"
                        + (
                            "Autorisation de sortie disponible ce mois."
                            if autorisation.disponible else
                            "Autorisation de sortie deja epuisee ce mois."
                        )
                    )
                }

        setattr(pointage, champ, heure)
        pointage.save()

        # Scan et autorisation dans la même transaction → cohérence garantie
        scan = Scan.objects.create(
            employe=employe, site=site,
            timestamp=now, type_scan=type_scan,
            pointage=pointage
        )

        if confirmer_autorisation and 'sortie' in type_scan:
            from .models import AutorisationSortie
            autorisation = AutorisationSortie.get_ou_creer_du_mois(employe, date_courante)
            if autorisation.disponible:
                autorisation.utilisee          = True
                autorisation.date_utilisation  = now
                autorisation.heure_depart_reel = heure
                autorisation.pointage          = pointage
                autorisation.save()
                AlerteRH.objects.create(
                    employe=employe,
                    type='SORTIE_ANTICIPEE',
                    detail=(
                        f"Sortie anticipée confirmée le {date_courante} "
                        f"à {heure.strftime('%H:%M')} sur {site.nom} "
                        f"— autorisation du mois utilisée."
                    ),
                    timestamp=now
                )
            else:
                AlerteRH.objects.create(
                    employe=employe,
                    type='SORTIE_NON_AUTORISEE',
                    detail=(
                        f"Sortie anticipée NON autorisée le {date_courante} "
                        f"à {heure.strftime('%H:%M')} sur {site.nom} "
                        f"— quota mensuel épuisé."
                    ),
                    timestamp=now
                )

    labels = {
        'entree_matin':        f"Entree matin enregistree a {heure.strftime('%H:%M')}",
        'sortie_matin':        f"Sortie matin enregistree a {heure.strftime('%H:%M')}",
        'entree_apres_midi':   f"Entree apres-midi enregistree a {heure.strftime('%H:%M')}",
        'sortie_apres_midi':   f"Sortie apres-midi enregistree a {heure.strftime('%H:%M')}",
    }

    return {
        'status': 'success',
        'code': type_scan,
        'message': labels.get(type_scan, f"Scan enregistre a {heure.strftime('%H:%M')}"),
        'data': _build_response_data(scan, pointage, now)
    }





def _build_response_data(scan, pointage, now) -> dict:
    """Construit le dictionnaire de réponse standard."""
    return {
        'scan_id':          scan.id,
        'type_scan':        scan.type_scan,
        'type_scan_display': scan.get_type_scan_display(),
        'timestamp':        now.isoformat(),
        'employe': {
            'id':          scan.employe.id,
            'nom_complet': scan.employe.get_nom_complet(),
            'matricule':   scan.employe.matricule,
            'poste':       scan.employe.poste.nom if scan.employe.poste else None,
        },
        'site':             scan.site.nom,
        'periode':          pointage.periode,
        'type_journee':     pointage.type_journee,
        'date':             pointage.date_pointage.isoformat(),
        'heure_arrivee':    str(pointage.heure_arrivee) if pointage.heure_arrivee else None,
        'heure_depart':     str(pointage.heure_depart)  if pointage.heure_depart  else None,
    }


# ─── Parsing du QR code ───────────────────────────────────────────────────────

def parse_qr_data(raw: str) -> dict | None:
    """
    Parse le contenu brut du QR code.
    Format attendu : EMPLOYE:matricule:uuid_token

    split(':', 2) pour gérer les matricules qui contiendraient des ':'.
    Retourne {'matricule': ..., 'token': ...} ou None si invalide.
    """
    parts = raw.strip().split(':', 2)
    if len(parts) != 3 or parts[0] != 'EMPLOYE':
        return None
    return {'matricule': parts[1], 'token': parts[2]}