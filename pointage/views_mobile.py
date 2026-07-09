# pointage/views_mobile.py
#
# API pour l'application React Native.
# Toute la logique métier est déléguée à services.process_scan().

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from datetime import datetime, time

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from .models import Site, Employe, Pointage
from .services import process_scan, parse_qr_data


# ─── Test de connectivité ─────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class MobileTestAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return JsonResponse({
            'status':  'success',
            'message': 'API mobile Django fonctionne',
            'data': {
                'server_time': timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S'),
                'endpoint':    '/api/mobile/test/',
            }
        })


# ─── Liste des sites ──────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class MobileSitesAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            sites_data = []
            for site in Site.objects.all().order_by('nom'):
                sites_data.append({
                    'id':                         site.id,
                    'nom':                        site.nom,
                    'adresse':                    site.adresse,
                    'heure_ouverture_matin':      str(site.heure_ouverture_matin),
                    'heure_fermeture_matin':      str(site.heure_fermeture_matin),
                    'heure_ouverture_apres_midi': str(site.heure_ouverture_apres_midi),
                    'heure_fermeture_apres_midi': str(site.heure_fermeture_apres_midi),
                })
            return JsonResponse({
                'status':  'success',
                'message': f'{len(sites_data)} sites récupérés',
                'data':    sites_data
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ─── Scan principal ───────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class MobileRecordScanAPIView(APIView):
    """
    Endpoint unique de scan.
    Reçoit le QR brut + site_id + mode optionnel ('auto' ou 'garde').
    Délègue 100 % de la logique à process_scan().
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'status': 'error', 'message': 'JSON invalide'}, status=400)

        raw_qr                 = data.get('employee_qr', '').strip()
        site_id                = data.get('site_id')
        mode                   = data.get('mode', 'auto')
        force_sortie           = bool(data.get('force_sortie', False))
        confirmer_autorisation = bool(data.get('confirmer_autorisation', False))
        force_new_garde        = bool(data.get('force_new', False))

        # Normaliser le mode
        if mode in ['night', 'nuit']:
            mode = 'garde'

        if not raw_qr:
            return JsonResponse({'status': 'error', 'message': 'QR code manquant'}, status=400)
        if not site_id:
            return JsonResponse({'status': 'error', 'message': 'site_id manquant'}, status=400)

        # Parser le QR code
        parsed = parse_qr_data(raw_qr)
        if not parsed:
            return JsonResponse({
                'status':  'error',
                'code':    'QR_FORMAT_INVALIDE',
                'message': 'Format QR invalide. Attendu : EMPLOYE:matricule:token'
            }, status=400)

        # Appel au service central
        result = process_scan(
            matricule=parsed['matricule'],
            qr_token=parsed['token'],
            site_id=int(site_id),
            mode=mode,
            force_sortie=force_sortie,
            confirmer_autorisation=confirmer_autorisation,
            force_new_garde=force_new_garde,
        )

        http_status = 201 if result['status'] == 'success' else (
            400 if result['status'] == 'error' else 200
        )
        return JsonResponse(result, status=http_status)


# ─── Vérification état du scan (helper UI) ───────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class MobileCheckFirstScanAPIView(APIView):
    """
    Indique à l'app quel sera le prochain scan attendu pour cet employé.
    Rôle purement informatif (aide UI) — la décision finale reste dans process_scan().
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'status': 'error', 'message': 'JSON invalide'}, status=400)

        raw_qr  = data.get('employee_qr', '').strip()
        site_id = data.get('site_id')

        if not raw_qr or not site_id:
            return JsonResponse({'status': 'error', 'message': 'employee_qr et site_id requis'}, status=400)

        parsed = parse_qr_data(raw_qr)
        if not parsed:
            return JsonResponse({'status': 'error', 'message': 'Format QR invalide'}, status=400)

        try:
            employe = Employe.objects.get(
                matricule=parsed['matricule'],
                qr_code_token=parsed['token'],
                actif=True
            )
        except Employe.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Employé non trouvé ou QR invalide'}, status=404)

        try:
            site = Site.objects.get(id=site_id)
        except Site.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f'Site {site_id} introuvable'}, status=404)

        now           = timezone.localtime(timezone.now())
        date_courante = now.date()
        heure         = now.time()

        # Garde en cours ?
        garde_en_cours = Pointage.objects.filter(
            employe=employe, periode='nuit', type_journee='garde',
            heure_depart__isnull=True
        ).order_by('-date_pointage').first()

        if garde_en_cours:
            return JsonResponse({
                'status': 'success',
                'data': {
                    'prochain_scan': 'fin_garde',
                    'mode_attendu':  'garde',
                    'employe':       _employe_dict(employe),
                    'site':          {'id': site.id, 'nom': site.nom},
                    'garde_en_cours': {
                        'id':            garde_en_cours.id,
                        'date_pointage': garde_en_cours.date_pointage.isoformat(),
                        'heure_arrivee': str(garde_en_cours.heure_arrivee),
                    }
                }
            })

        # Garde planifiée ?
        garde_planifiee = Pointage.objects.filter(
            employe=employe, date_pointage=date_courante,
            periode='nuit', type_journee='garde', heure_arrivee__isnull=True
        ).first()

        if garde_planifiee:
            return JsonResponse({
                'status': 'success',
                'data': {
                    'prochain_scan': 'debut_garde',
                    'mode_attendu':  'garde',
                    'employe':       _employe_dict(employe),
                    'site':          {'id': site.id, 'nom': site.nom},
                }
            })

        # Pointages normaux — déterminer le prochain parmi E1/S1/E2/S2
        prochain = _prochain_scan_normal(employe, date_courante, heure)

        return JsonResponse({
            'status': 'success',
            'data': {
                'prochain_scan': prochain,
                'mode_attendu':  'normal',
                'employe':       _employe_dict(employe),
                'site':          {'id': site.id, 'nom': site.nom},
                'date':          date_courante.isoformat(),
            }
        })


# ─── Période courante ─────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class MobileCurrentPeriodAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        now    = timezone.localtime(timezone.now())
        heure  = now.time()
        periode = 'matin' if heure < time(12, 0) else 'apres_midi'
        return JsonResponse({
            'status': 'success',
            'data': {
                'current_time': now.isoformat(),
                'periode':      periode,
                'date':         now.date().isoformat(),
                'heure':        heure.strftime('%H:%M:%S'),
            }
        })


# ─── Pointages d'un employé ───────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class MobilePointagesAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        raw_qr    = request.GET.get('employee_qr', '').strip()
        matricule = request.GET.get('matricule', '').strip()
        date_str  = request.GET.get('date')

        # Support double mode : QR complet ou matricule seul (rétrocompat)
        if raw_qr:
            parsed = parse_qr_data(raw_qr)
            if not parsed:
                return JsonResponse({'status': 'error', 'message': 'Format QR invalide'}, status=400)
            try:
                employe = Employe.objects.get(
                    matricule=parsed['matricule'],
                    qr_code_token=parsed['token'],
                    actif=True
                )
            except Employe.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'QR invalide'}, status=404)
        elif matricule:
            # Compatibilité ascendante — matricule seul (sans vérif token)
            if ':' in matricule:
                parts = matricule.split(':')
                matricule = parts[1] if len(parts) >= 2 else matricule
            try:
                employe = Employe.objects.get(matricule=matricule, actif=True)
            except Employe.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': f'Employé {matricule} non trouvé'}, status=404)
        else:
            return JsonResponse({'status': 'error', 'message': 'employee_qr ou matricule requis'}, status=400)

        if date_str:
            try:
                date_courante = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'status': 'error', 'message': 'Format date invalide (YYYY-MM-DD)'}, status=400)
        else:
            date_courante = timezone.localtime(timezone.now()).date()

        pointages = Pointage.objects.filter(
            employe=employe, date_pointage=date_courante
        ).select_related('site').order_by('periode')

        pointages_data = [{
            'id':                 p.id,
            'periode':            p.periode,
            'type_journee':       p.type_journee,
            'site':               p.site.nom if p.site else None,
            'site_id':            p.site.id  if p.site else None,
            'heure_arrivee':      str(p.heure_arrivee)       if p.heure_arrivee      else None,
            'heure_depart':       str(p.heure_depart)        if p.heure_depart       else None,
            'retard':             str(p.retard)              if p.retard             else None,
            'heures_travaillees': str(p.heures_travaillees)  if p.heures_travaillees else None,
            'statut':             p.statut,
            'date_pointage':      p.date_pointage.isoformat(),
        } for p in pointages]

        return JsonResponse({
            'status': 'success',
            'data': {
                'employe':         _employe_dict(employe),
                'date':            date_courante.isoformat(),
                'pointages':       pointages_data,
                'total_pointages': len(pointages_data),
            }
        })


# ─── Helpers internes ─────────────────────────────────────────────────────────

def _employe_dict(employe) -> dict:
    return {
        'id':          employe.id,
        'nom_complet': employe.get_nom_complet(),
        'matricule':   employe.matricule,
        'poste':       employe.poste.nom if employe.poste else None,
    }


def _prochain_scan_normal(employe, date_courante, heure_courante) -> str:
    """Retourne le code du prochain scan attendu dans la séquence E1→S1→E2→S2."""
    for periode in ['matin', 'apres_midi']:
        p = Pointage.objects.filter(
            employe=employe, date_pointage=date_courante, periode=periode
        ).first()
        if not p or not p.heure_arrivee:
            return f'entree_{periode}'
        if not p.heure_depart:
            return f'sortie_{periode}'
    return 'journee_complete'


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint : tableau de bord du jour — tous les scans (vue superviseur)
# GET /api/mobile/pointages/today/?date=YYYY-MM-DD&site_id=N
# ─────────────────────────────────────────────────────────────────────────────
class MobileTodayPointagesAPIView(APIView):
    """
    Retourne TOUS les pointages d'une journée (par défaut aujourd'hui),
    triés du plus récent au plus ancien, avec les infos employé.

    Paramètres optionnels :
      ?date=YYYY-MM-DD   — date ciblée (défaut : aujourd'hui)
      ?site_id=N         — filtre par site
      ?refresh=1         — ignoré côté serveur, utile pour forcer le rechargement côté client
    """
    permission_classes = [AllowAny]

    def get(self, request):
        # Date
        date_str = request.GET.get('date', '').strip()
        if date_str:
            try:
                date_cible = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'status': 'error', 'message': 'Format date invalide (YYYY-MM-DD)'}, status=400)
        else:
            date_cible = timezone.localtime(timezone.now()).date()

        # Queryset de base
        qs = Pointage.objects.filter(date_pointage=date_cible).select_related('employe', 'site', 'employe__poste')

        # Filtre site optionnel
        site_id = request.GET.get('site_id', '').strip()
        if site_id:
            try:
                qs = qs.filter(site_id=int(site_id))
            except (ValueError, TypeError):
                pass

        # Tri : heure d'arrivée décroissante (les plus récents en premier)
        qs = qs.order_by('-heure_arrivee', '-id')

        data = []
        for p in qs:
            data.append({
                'id':                 p.id,
                'employe_nom':        p.employe.get_nom_complet(),
                'employe_matricule':  p.employe.matricule,
                'employe_poste':      p.employe.poste.nom if p.employe.poste else None,
                'site':               p.site.nom if p.site else None,
                'site_id':            p.site.id  if p.site else None,
                'date_pointage':      p.date_pointage.isoformat(),
                'periode':            p.periode,
                'type_journee':       p.type_journee,
                'heure_arrivee':      str(p.heure_arrivee)         if p.heure_arrivee       else None,
                'heure_depart':       str(p.heure_depart)          if p.heure_depart        else None,
                'retard':             str(p.retard)                if p.retard              else None,
                'heures_travaillees': str(p.heures_travaillees)    if p.heures_travaillees  else None,
                'statut':             p.statut,
            })

        return JsonResponse({
            'status': 'success',
            'date':   date_cible.isoformat(),
            'count':  len(data),
            'data':   data,
        })