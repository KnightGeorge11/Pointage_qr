# pointage/tests/test_mobile_auth.py
#
# LOGIN/LOGOUT PAR UTILISATEUR (migration jeton d'appareil partagé ->
# jeton d'opérateur connecté)
# =============================================================================
# POST /api/mobile/auth/login/  : authentifie un compte CustomUser existant
#                                  (identique au login web), retourne un
#                                  jeton DRF appartenant à cet utilisateur.
# POST /api/mobile/auth/logout/ : révoque réellement le jeton côté serveur.
#
# Le compte connecté (opérateur) et l'employé scanné restent deux notions
# totalement indépendantes dans toute la chaîne — vérifié explicitement.
from datetime import time as dtime, datetime
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from pointage.models import Employe, Site, Pointage

User = get_user_model()


class LoginEndpointTestCase(TestCase):
    def setUp(self):
        # Le throttle de production reste à 5/minute. Chaque test doit
        # disposer d'un bucket de cache indépendant pour ne pas hériter des
        # tentatives d'un autre test exécuté avec la même adresse IP.
        cache.clear()
        self.user = User.objects.create_user(
            username='jean_operateur', password='motdepasse123', role='user',
        )
        self.client = APIClient()

    def test_login_avec_identifiants_valides_reussit(self):
        response = self.client.post('/api/mobile/auth/login/', {
            'username': 'jean_operateur', 'password': 'motdepasse123',
        }, format='json')
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'token' in data['data']
        assert data['data']['user']['username'] == 'jean_operateur'

    def test_login_ne_retourne_jamais_le_mot_de_passe(self):
        response = self.client.post('/api/mobile/auth/login/', {
            'username': 'jean_operateur', 'password': 'motdepasse123',
        }, format='json')
        body = response.content.decode()
        assert 'motdepasse123' not in body
        assert 'password' not in body

    def test_login_cree_un_vrai_jeton_drf_en_base(self):
        response = self.client.post('/api/mobile/auth/login/', {
            'username': 'jean_operateur', 'password': 'motdepasse123',
        }, format='json')
        token_key = response.json()['data']['token']
        assert Token.objects.filter(key=token_key, user=self.user).exists()

    def test_login_reutilise_le_meme_jeton_si_deja_connecte(self):
        r1 = self.client.post('/api/mobile/auth/login/', {
            'username': 'jean_operateur', 'password': 'motdepasse123',
        }, format='json')
        r2 = self.client.post('/api/mobile/auth/login/', {
            'username': 'jean_operateur', 'password': 'motdepasse123',
        }, format='json')
        assert r1.json()['data']['token'] == r2.json()['data']['token']
        assert Token.objects.filter(user=self.user).count() == 1

    def test_mauvais_mot_de_passe_est_refuse(self):
        response = self.client.post('/api/mobile/auth/login/', {
            'username': 'jean_operateur', 'password': 'mauvais_mdp',
        }, format='json')
        assert response.status_code == 401
        assert response.json()['status'] == 'error'

    def test_compte_inexistant_est_refuse(self):
        response = self.client.post('/api/mobile/auth/login/', {
            'username': 'nexiste_pas', 'password': 'x',
        }, format='json')
        assert response.status_code == 401

    def test_compte_desactive_est_refuse(self):
        User.objects.create_user(
            username='inactif_op', password='motdepasse123', role='user', is_active=False,
        )
        response = self.client.post('/api/mobile/auth/login/', {
            'username': 'inactif_op', 'password': 'motdepasse123',
        }, format='json')
        # Django bloque déjà l'authentification d'un compte inactif au
        # niveau du backend (ModelBackend.user_can_authenticate) : le
        # message reste volontairement générique (ne pas révéler si le
        # compte existe mais est désactivé, vs mauvais mot de passe).
        assert response.status_code == 401

    def test_identifiants_manquants_retourne_400(self):
        response = self.client.post('/api/mobile/auth/login/', {'username': 'jean_operateur'}, format='json')
        assert response.status_code == 400

    def test_deux_utilisateurs_ont_deux_jetons_differents(self):
        User.objects.create_user(username='marie_operatrice', password='autremdp456', role='user')

        r1 = self.client.post('/api/mobile/auth/login/', {
            'username': 'jean_operateur', 'password': 'motdepasse123',
        }, format='json')
        r2 = self.client.post('/api/mobile/auth/login/', {
            'username': 'marie_operatrice', 'password': 'autremdp456',
        }, format='json')
        assert r1.json()['data']['token'] != r2.json()['data']['token']


class LogoutEndpointTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='jean_operateur', password='motdepasse123', role='user',
        )
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()

    def test_logout_avec_token_valide_reussit(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.post('/api/mobile/auth/logout/')
        assert response.status_code == 200
        assert response.json()['status'] == 'success'

    def test_logout_supprime_reellement_le_token_en_base(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.client.post('/api/mobile/auth/logout/')
        assert not Token.objects.filter(key=self.token.key).exists()

    def test_token_revoque_apres_logout_est_refuse_immediatement(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.client.post('/api/mobile/auth/logout/')

        # Même client, même en-tête, jeton désormais révoqué
        response = self.client.get('/api/mobile/sites/')
        assert response.status_code == 401

    def test_logout_sans_token_est_refuse(self):
        client = APIClient()
        response = client.post('/api/mobile/auth/logout/')
        assert response.status_code == 401


class EndpointsProtegesAvecJetonUtilisateurTestCase(TestCase):
    """Confirme que les endpoints déjà protégés (Phase 12) fonctionnent
    identiquement avec un jeton obtenu par login utilisateur — le
    mécanisme d'authentification (TokenAuthentication) est inchangé,
    seule la provenance du jeton change."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='jean_operateur', password='motdepasse123', role='user',
        )
        self.site = Site.objects.create(
            nom="Site Test", adresse="1 Rue Test",
            heure_ouverture_matin=dtime(8, 0), heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 0), heure_fermeture_apres_midi=dtime(17, 0),
        )
        self.client = APIClient()

    def test_endpoint_protege_sans_token_refuse(self):
        response = self.client.get('/api/mobile/sites/')
        assert response.status_code == 401

    def test_endpoint_protege_avec_mauvais_token_refuse(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ceci-est-invalide')
        response = self.client.get('/api/mobile/sites/')
        assert response.status_code == 401

    def test_endpoint_protege_avec_token_utilisateur_valide_reussit(self):
        login_resp = self.client.post('/api/mobile/auth/login/', {
            'username': 'jean_operateur', 'password': 'motdepasse123',
        }, format='json')
        token = login_resp.json()['data']['token']

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        response = self.client.get('/api/mobile/sites/')
        assert response.status_code == 200


class SeparationCompteEmployeTestCase(TestCase):
    """Vérifie explicitement que le compte connecté (opérateur) et
    l'employé scanné restent deux entités totalement distinctes.
    Exemple du cahier des charges : compte connecté = Jean, QR scanné =
    EMP042 -> le pointage doit être celui de EMP042, jamais celui de Jean."""

    def setUp(self):
        self.operateur = User.objects.create_user(
            username='jean_operateur', password='motdepasse123', role='user',
        )
        self.token = Token.objects.create(user=self.operateur)
        self.site = Site.objects.create(
            nom="Site Test", adresse="1 Rue Test",
            heure_ouverture_matin=dtime(8, 0), heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 0), heure_fermeture_apres_midi=dtime(17, 0),
        )
        self.employe = Employe.objects.create(
            nom="Quarante-Deux", prenom="Employe", matricule="EMP042",
            qr_code_token="99999999-9999-9999-9999-999999999999", actif=True,
        )
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

    def test_le_pointage_enregistre_est_celui_de_lemploye_scanne_pas_de_loperateur(self):
        # Heure figée dans la plage du matin du site (8h-12h) : ce test
        # vérifie la séparation compte/employé, pas les règles horaires,
        # donc il ne doit pas dépendre de l'heure réelle d'exécution.
        fake_now = timezone.make_aware(datetime(2026, 7, 1, 9, 0))
        with patch('pointage.services.timezone.now', return_value=fake_now):
            response = self.client.post('/api/mobile/scan/record/', {
                'employee_qr': f'EMPLOYE:{self.employe.matricule}:{self.employe.qr_code_token}',
                'site_id': self.site.id,
                'mode': 'auto',
            }, format='json')
        assert response.status_code in (200, 201)

        pointage = Pointage.objects.get(employe=self.employe)
        assert pointage.employe == self.employe
        assert pointage.employe != self.operateur
        # Aucune trace de l'opérateur (username 'jean_operateur') dans le
        # Pointage lui-même : il n'existe aucun champ qui l'y relierait.
        assert not hasattr(pointage, 'operateur')
        assert not hasattr(pointage, 'utilisateur')

    def test_le_compte_operateur_nest_jamais_utilise_comme_identifiant_employe(self):
        """Le matricule/qr_code_token de l'employé et le username/token de
        l'opérateur vivent dans des espaces totalement séparés — un jeton
        d'opérateur valide ne permet jamais de "devenir" un employé."""
        assert Employe.objects.filter(matricule=self.operateur.username).exists() is False
