# pointage/views_mobile.py
#
# API pour l'application React Native.
# Toute la logique métier est déléguée à services.process_scan().

import json
import logging
import uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.contrib.auth import authenticate
from datetime import datetime, time

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token

from .models import Site, Employe, Pointage
from .services import process_scan, parse_qr_data

logger = logging.getLogger(__name__)


class MobileAuthenticatedAPIView(APIView):
    """
    Base commune à tous les endpoints mobiles qui exposent des données ou
    écrivent en base (sécurité API mobile).

    Utilise TokenAuthentication (rest_framework.authtoken, déjà présent
    dans INSTALLED_APPS) : un jeton envoyé via l'en-tête
    `Authorization: Token <clé>`. Depuis la migration vers le login
    utilisateur, ce jeton est obtenu via MobileLoginAPIView (identifiant +
    mot de passe d'un compte CustomUser existant) et appartient à
    l'OPÉRATEUR connecté — jamais à l'employé scanné, qui reste identifié
    uniquement par son QR (EMPLOYE:matricule:token), totalement indépendant
    de ce jeton d'authentification applicative.

    N'importe qui ne peut donc plus lire l'historique ou enregistrer un
    scan simplement en connaissant l'URL — il faut être connecté.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]


# ─── Authentification (login/logout par utilisateur) ──────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class MobileLoginAPIView(APIView):
    """
    POST /api/mobile/auth/login/ — {"username": ..., "password": ...}

    Authentifie un compte CustomUser déjà existant (identique au login web,
    même authenticate() Django) et retourne son jeton DRF (créé s'il
    n'existe pas encore, réutilisé sinon — un seul jeton actif par
    utilisateur). Ce jeton identifie l'OPÉRATEUR de l'application, jamais
    l'employé qui sera scanné ensuite : les deux notions restent
    totalement indépendantes dans tout le reste de l'API.

    Public par nécessité (c'est le moyen d'obtenir une authentification),
    mais ne retourne jamais le mot de passe ni aucune donnée sensible.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, TypeError):
            data = request.POST

        username = (data.get('username') or '').strip()
        password = data.get('password') or ''

        if not username or not password:
            return JsonResponse({
                'status': 'error', 'code': 'IDENTIFIANTS_MANQUANTS',
                'message': "Nom d'utilisateur et mot de passe requis."
            }, status=400)

        user = authenticate(request, username=username, password=password)

        if user is None:
            return JsonResponse({
                'status': 'error', 'code': 'IDENTIFIANTS_INVALIDES',
                'message': "Nom d'utilisateur ou mot de passe incorrect."
            }, status=401)

        if not user.is_active:
            return JsonResponse({
                'status': 'error', 'code': 'COMPTE_DESACTIVE',
                'message': "Ce compte est désactivé."
            }, status=403)

        token, _ = Token.objects.get_or_create(user=user)

        return JsonResponse({
            'status': 'success',
            'data': {
                'token': token.key,
                'user': {
                    'username':   user.username,
                    'first_name': user.first_name,
                    'last_name':  user.last_name,
                    'is_staff':   user.is_staff,
                },
            }
        }, status=200)


@method_decorator(csrf_exempt, name='dispatch')
class MobileLogoutAPIView(MobileAuthenticatedAPIView):
    """
    POST /api/mobile/auth/logout/ — révoque réellement le jeton côté
    serveur (pas seulement un oubli côté client) : après logout, ce jeton
    précis renvoie 401 sur tout endpoint protégé, immédiatement.
    """
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return JsonResponse({'status': 'success', 'message': 'Déconnecté.'})


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
class MobileSitesAPIView(MobileAuthenticatedAPIView):

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
        except Exception:
            logger.exception("Erreur inattendue lors de la récupération des sites mobiles")
            return JsonResponse({
                'status': 'error',
                'code': 'ERREUR_SERVEUR',
                'message': 'Erreur interne du serveur.'
            }, status=500)


# ─── Scan principal ───────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class MobileRecordScanAPIView(MobileAuthenticatedAPIView):
    """
    Endpoint unique de scan.
    Reçoit le QR brut + site_id + mode optionnel ('auto' ou 'garde').
    Délègue 100 % de la logique à process_scan().
    """

    def post(self, request):
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'status': 'error', 'message': 'JSON invalide'}, status=400)

        raw_qr = data.get('employee_qr', '').strip()
        site_id = data.get('site_id')
        mode = data.get('mode', 'auto')
        force_new_garde = _parse_bool(data.get('force_new', False), default=False)
        client_event_id = data.get('client_event_id')
        captured_at_raw = data.get('captured_at')
        captured_at = None
        if client_event_id:
            try: client_event_id = uuid.UUID(str(client_event_id))
            except (ValueError, TypeError, AttributeError):
                return JsonResponse({'status':'error','code':'CLIENT_EVENT_ID_INVALIDE','message':'client_event_id invalide.'}, status=400)
        if captured_at_raw:
            try:
                captured_at = datetime.fromisoformat(str(captured_at_raw).replace('Z', '+00:00'))
                if timezone.is_naive(captured_at): captured_at = timezone.make_aware(captured_at, timezone.get_current_timezone())
                else: captured_at = timezone.localtime(captured_at)
            except (ValueError, TypeError):
                return JsonResponse({'status':'error','code':'CAPTURED_AT_INVALIDE','message':'captured_at invalide.'}, status=400)
        if force_new_garde is None:
            return JsonResponse({
                'status': 'error',
                'code': 'FORCE_NEW_INVALIDE',
                'message': 'force_new doit être un booléen (true/false).',
            }, status=400)

        MODE_NORMALISATION = {
            'day': 'auto', 'auto': 'auto',
            'night': 'garde', 'nuit': 'garde', 'garde': 'garde',
        }
        if mode not in MODE_NORMALISATION:
            return JsonResponse({
                'status': 'error',
                'code': 'MODE_INVALIDE',
                'message': f"mode invalide : '{mode}'. Valeurs acceptées : day, night, auto, garde."
            }, status=400)
        mode = MODE_NORMALISATION[mode]

        if not raw_qr:
            return JsonResponse({'status': 'error', 'message': 'QR code manquant'}, status=400)
        if not site_id:
            return JsonResponse({'status': 'error', 'message': 'site_id manquant'}, status=400)

        parsed = parse_qr_data(raw_qr)
        if not parsed:
            return JsonResponse({
                'status': 'error',
                'code': 'QR_FORMAT_INVALIDE',
                'message': 'Format QR invalide. Attendu : EMPLOYE:matricule:token'
            }, status=400)

        try:
            site_id = int(site_id)
        except (TypeError, ValueError):
            return JsonResponse({
                'status': 'error',
                'code': 'SITE_INVALIDE',
                'message': 'site_id invalide'
            }, status=400)

        result = process_scan(
            matricule=parsed['matricule'],
            qr_token=parsed['token'],
            site_id=site_id,
            mode=mode,
            force_new_garde=force_new_garde,
            client_event_id=client_event_id,
            captured_at=captured_at,
        )

        http_status = 201 if result['status'] == 'success' else (
            400 if result['status'] == 'error' else 200
        )
        return JsonResponse(result, status=http_status)


# ─── Vérification état du scan (helper UI) ───────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class MobileCheckFirstScanAPIView(MobileAuthenticatedAPIView):
    """
    Indique à l'app quel sera le prochain scan attendu pour cet employé.
    Rôle purement informatif (aide UI) — la décision finale reste dans process_scan().
    """

    def post(self, request):
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'status': 'error', 'message': 'JSON invalide'}, status=400)

        raw_qr = data.get('employee_qr', '').strip()
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
            site_id = int(site_id)
        except (TypeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'site_id invalide'}, status=400)

        try:
            site = Site.objects.get(id=site_id)
        except Site.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f'Site {site_id} introuvable'}, status=404)

        now = timezone.localtime(timezone.now())
        date_courante = now.date()
        heure = now.time()

        garde_en_cours = Pointage.objects.filter(
            employe=employe, periode='nuit', type_journee='garde',
            heure_depart__isnull=True
        ).order_by('-date_pointage').first()

        if garde_en_cours:
            return JsonResponse({
                'status': 'success',
                'data': {
                    'prochain_scan': 'fin_garde',
                    'mode_attendu': 'garde',
                    'employe': _employe_dict(employe),
                    'site': {'id': site.id, 'nom': site.nom},
                    'garde_en_cours': {
                        'id': garde_en_cours.id,
                        'date_pointage': garde_en_cours.date_pointage.isoformat(),
                        'heure_arrivee': str(garde_en_cours.heure_arrivee),
                    }
                }
            })

        garde_planifiee = Pointage.objects.filter(
            employe=employe, date_pointage=date_courante,
            periode='nuit', type_journee='garde', heure_arrivee__isnull=True
        ).first()

        if garde_planifiee:
            return JsonResponse({
                'status': 'success',
                'data': {
                    'prochain_scan': 'debut_garde',
                    'mode_attendu': 'garde',
                    'employe': _employe_dict(employe),
                    'site': {'id': site.id, 'nom': site.nom},
                }
            })

        prochain = _prochain_scan_normal(employe, date_courante, heure)

        return JsonResponse({
            'status': 'success',
            'data': {
                'prochain_scan': prochain,
                'mode_attendu': 'normal',
                'employe': _employe_dict(employe),
                'site': {'id': site.id, 'nom': site.nom},
                'date': date_courante.isoformat(),
            }
        })


# ─── Période courante ─────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class MobileCurrentPeriodAPIView(MobileAuthenticatedAPIView):

    def get(self, request):
        now = timezone.localtime(timezone.now())
        heure = now.time()
        periode = 'matin' if heure < time(12, 0) else 'apres_midi'
        return JsonResponse({
            'status': 'success',
            'data': {
                'current_time': now.isoformat(),
                'periode': periode,
                'date': now.date().isoformat(),
                'heure': heure.strftime('%H:%M:%S'),
            }
        })


# ─── Pointages d'un employé ───────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class MobilePointagesAPIView(MobileAuthenticatedAPIView):

    def get(self, request):
        raw_qr = request.GET.get('employee_qr', '').strip()
        date_str = request.GET.get('date')

        if not raw_qr:
            return JsonResponse({'status': 'error', 'message': 'employee_qr requis'}, status=400)

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

        if date_str:
            try:
                date_courante = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'status': 'error', 'message': 'Format date invalide (YYYY-MM-DD)'}, status=400)
        else:
            date_courante = timezone.localtime(timezone.now()).date()

        from django.db.models import Q

        pointages = Pointage.objects.filter(
            Q(employe=employe, date_pointage=date_courante)
            | Q(employe=employe, periode='nuit', date_depart=date_courante)
        ).select_related('site').order_by('date_pointage', 'periode')

        pointages_data = [{
            'id': p.id,
            'periode': p.periode,
            'type_journee': p.type_journee,
            'site': p.site.nom if p.site else None,
            'site_id': p.site.id if p.site else None,
            'heure_arrivee': str(p.heure_arrivee) if p.heure_arrivee else None,
            'heure_depart': str(p.heure_depart) if p.heure_depart else None,
            'retard': str(p.retard) if p.retard else None,
            'heures_travaillees': str(p.heures_travaillees) if p.heures_travaillees else None,
            'statut': p.statut,
            'date_pointage': p.date_pointage.isoformat(),
        } for p in pointages]

        return JsonResponse({
            'status': 'success',
            'data': {
                'employe': _employe_dict(employe),
                'date': date_courante.isoformat(),
                'pointages': pointages_data,
                'total_pointages': len(pointages_data),
            }
        })


# ─── Helpers internes ─────────────────────────────────────────────────────────

def _parse_bool(value, default=False):
    """Parse strictement un booléen venant du JSON/API."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ('true', '1', 'yes', 'oui'):
            return True
        if normalized in ('false', '0', 'no', 'non'):
            return False
    return None


def _employe_dict(employe) -> dict:
    return {
        'id': employe.id,
        'nom_complet': employe.get_nom_complet(),
        'matricule': employe.matricule,
        'poste': employe.poste.nom if employe.poste else None,
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
class MobileTodayPointagesAPIView(MobileAuthenticatedAPIView):
    """
    Retourne TOUS les pointages d'une journée (par défaut aujourd'hui),
    triés du plus récent au plus ancien, avec les infos employé.

    Paramètres optionnels :
      ?date=YYYY-MM-DD   — date ciblée (défaut : aujourd'hui)
      ?site_id=N         — filtre par site
      ?refresh=1         — ignoré côté serveur, utile pour forcer le rechargement côté client
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        date_str = request.GET.get('date', '').strip()
        if date_str:
            try:
                date_cible = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'status': 'error', 'message': 'Format date invalide (YYYY-MM-DD)'}, status=400)
        else:
            date_cible = timezone.localtime(timezone.now()).date()

        qs = Pointage.objects.filter(date_pointage=date_cible).select_related('employe', 'site', 'employe__poste')

        site_id = request.GET.get('site_id', '').strip()
        if site_id:
            try:
                qs = qs.filter(site_id=int(site_id))
            except (ValueError, TypeError):
                return JsonResponse({
                    'status': 'error',
                    'code': 'SITE_INVALIDE',
                    'message': 'site_id invalide'
                }, status=400)

        qs = qs.order_by('-heure_arrivee', '-id')

        data = []
        for p in qs:
            data.append({
                'id': p.id,
                'employe_nom': p.employe.get_nom_complet(),
                'employe_matricule': p.employe.matricule,
                'employe_poste': p.employe.poste.nom if p.employe.poste else None,
                'site': p.site.nom if p.site else None,
                'site_id': p.site.id if p.site else None,
                'date_pointage': p.date_pointage.isoformat(),
                'periode': p.periode,
                'type_journee': p.type_journee,
                'heure_arrivee': str(p.heure_arrivee) if p.heure_arrivee else None,
                'heure_depart': str(p.heure_depart) if p.heure_depart else None,
                'retard': str(p.retard) if p.retard else None,
                'heures_travaillees': str(p.heures_travaillees) if p.heures_travaillees else None,
                'statut': p.statut,
            })

        return JsonResponse({
            'status': 'success',
            'date': date_cible.isoformat(),
            'count': len(data),
            'data': data,
        })
