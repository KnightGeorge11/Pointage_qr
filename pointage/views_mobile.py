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
from datetime import datetime

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token

from .models import Site, Employe, Pointage
from .services import process_scan, parse_qr_data
from .mobile_throttle import MobileLoginRateThrottle

logger = logging.getLogger(__name__)

# La validation métier de captured_at est centralisée dans services.process_scan().
# Les vues mobiles ne doivent pas appliquer une politique différente (le service
# accepte au maximum 24 h de décalage vers le passé et 5 min vers le futur).


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
    throttle_classes = [MobileLoginRateThrottle]

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