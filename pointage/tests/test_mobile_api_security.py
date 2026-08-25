# pointage/tests/test_mobile_api_security.py
#
# SÉCURITÉ DE L'API MOBILE (Phase 12)
# ====================================
# Avant : tous les endpoints /api/mobile/... utilisaient AllowAny + csrf_exempt,
# permettant à n'importe qui de lire l'historique (ex: ?matricule=E001) ou
# d'enregistrer un scan sans aucune authentification.
#
# Après : TokenAuthentication (rest_framework.authtoken, déjà installé) sur
# tous les endpoints sauf /api/mobile/test/ (simple ping, aucune donnée).
from datetime import time as dtime, date

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from pointage.models import Employe, Site, Pointage

User = get_user_model()


class MobileApiSecurityTestCase(TestCase):
    def setUp(self):
        self.site = Site.objects.create(
            nom="Site Sécu", adresse="1 Rue Test",
            heure_ouverture_matin=dtime(8, 0), heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 0), heure_fermeture_apres_midi=dtime(17, 0),
        )
        self.employe = Employe.objects.create(
            nom="Test", prenom="Sécu", matricule="SEC01", actif=True,
        )
        self.scanner_user = User.objects.create_user(username='scanner_sec_test', password='x')
        self.token = Token.objects.create(user=self.scanner_user)

    def test_sites_sans_token_est_refuse(self):
        client = APIClient()
        response = client.get('/api/mobile/sites/')
        assert response.status_code == 401

    def test_sites_avec_token_valide_est_autorise(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = client.get('/api/mobile/sites/')
        assert response.status_code == 200

    def test_sites_avec_token_invalide_est_refuse(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token token-invalide-inexistant')
        response = client.get('/api/mobile/sites/')
        assert response.status_code == 401

    def test_fuite_historique_par_matricule_sans_token_est_bloquee(self):
        """
        Cas précis signalé lors de l'audit : récupérer l'historique d'un
        employé via ?matricule=... sans authentification.
        """
        client = APIClient()
        response = client.get('/api/mobile/pointages/', {'matricule': self.employe.matricule})
        assert response.status_code == 401

    def test_record_scan_sans_token_est_refuse(self):
        client = APIClient()
        response = client.post('/api/mobile/scan/record/', {
            'employee_qr': f'EMPLOYE:{self.employe.matricule}:00000000-0000-0000-0000-000000000000',
            'site_id': self.site.id,
        }, format='json')
        assert response.status_code == 401

    def test_endpoint_test_reste_ouvert_sans_authentification(self):
        """/api/mobile/test/ est un simple ping de connectivité, sans donnée
        sensible : il reste volontairement accessible sans jeton."""
        client = APIClient()
        response = client.get('/api/mobile/test/')
        assert response.status_code == 200

    def test_today_pointages_sans_token_est_refuse(self):
        client = APIClient()
        response = client.get('/api/mobile/pointages/today/')
        assert response.status_code == 401

    def test_check_first_scan_sans_token_est_refuse(self):
        client = APIClient()
        response = client.post('/api/mobile/scan/check-first/', {
            'employee_qr': f'EMPLOYE:{self.employe.matricule}:00000000-0000-0000-0000-000000000000',
            'site_id': self.site.id,
        }, format='json')
        assert response.status_code == 401

    # ------------------------------------------------------------------
    # Dernière vérification de sécurité — couverture complète des 7
    # endpoints : token absent ET token invalide (pas seulement absent).
    # ------------------------------------------------------------------

    def test_current_period_sans_token_est_refuse(self):
        """MobileCurrentPeriodAPIView n'avait aucun test d'authentification."""
        client = APIClient()
        response = client.get('/api/mobile/periods/current/')
        assert response.status_code == 401

    def test_current_period_avec_token_invalide_est_refuse(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token ceci-nest-pas-un-token-valide')
        response = client.get('/api/mobile/periods/current/')
        assert response.status_code == 401

    def test_current_period_avec_token_valide_fonctionne(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = client.get('/api/mobile/periods/current/')
        assert response.status_code == 200

    def test_record_scan_avec_token_invalide_est_refuse(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token ceci-nest-pas-un-token-valide')
        response = client.post('/api/mobile/scan/record/', {
            'employee_qr': f'EMPLOYE:{self.employe.matricule}:00000000-0000-0000-0000-000000000000',
            'site_id': self.site.id,
        }, format='json')
        assert response.status_code == 401

    def test_check_first_scan_avec_token_invalide_est_refuse(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token ceci-nest-pas-un-token-valide')
        response = client.post('/api/mobile/scan/check-first/', {
            'employee_qr': f'EMPLOYE:{self.employe.matricule}:00000000-0000-0000-0000-000000000000',
            'site_id': self.site.id,
        }, format='json')
        assert response.status_code == 401

    def test_today_pointages_avec_token_invalide_est_refuse(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token ceci-nest-pas-un-token-valide')
        response = client.get('/api/mobile/pointages/today/')
        assert response.status_code == 401

    def test_check_first_scan_site_id_invalide_retourne_400_pas_500(self):
        """Bug trouvé pendant cette vérification de sécurité : Site.objects.get(id=site_id)
        n'était pas protégé, provoquant un 500 sur un site_id non numérique."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = client.post('/api/mobile/scan/check-first/', {
            'employee_qr': f'EMPLOYE:{self.employe.matricule}:{self.employe.qr_code_token}',
            'site_id': 'abc',
        }, format='json')
        assert response.status_code == 400

    def test_today_pointages_ne_permet_pas_de_cibler_un_employe_precis(self):
        """MobileTodayPointagesAPIView n'accepte aucun paramètre d'ENTRÉE
        employé/matricule/employee_qr : c'est un roster par site/date, pas
        un moyen de cibler un employé précis pour contourner
        MobilePointagesAPIView (qui exige employee_qr+token). Le mot
        'matricule' apparaît légitimement dans les champs de SORTIE
        (p.employe.matricule) : on vérifie ici l'absence de lecture d'un
        paramètre matricule/employe_id/employee_qr depuis la requête."""
        import inspect
        from pointage import views_mobile
        source = inspect.getsource(views_mobile.MobileTodayPointagesAPIView)
        assert "request.GET.get('matricule'" not in source
        assert "request.GET.get('employe_id'" not in source
        assert "request.GET.get('employee_qr'" not in source
        assert "request.GET['matricule']" not in source

    def test_mobile_test_ne_retourne_aucune_donnee_sensible(self):
        """Confirme explicitement le contenu exact de MobileTestAPIView :
        aucune donnée employé/site/pointage, uniquement un ping."""
        client = APIClient()
        response = client.get('/api/mobile/test/')
        data = response.json()
        assert set(data['data'].keys()) == {'server_time', 'endpoint'}
        assert 'employe' not in str(data).lower()
        assert 'matricule' not in str(data).lower()


class HistoriqueParEmployeTestCase(TestCase):
    """
    Correction de la fuite : GET /api/mobile/pointages/?matricule=E001
    permettait à n'importe quel appareil authentifié (jeton scanner) de lire
    l'historique de N'IMPORTE QUEL employé, sans preuve de possession de son
    QR. Le mode "matricule seul" a été retiré (confirmé mort côté mobile ET
    desktop) ; seul employee_qr (matricule + token UUID) est accepté.
    """
    def setUp(self):
        self.site = Site.objects.create(
            nom="Site A", adresse="1 Rue Test",
            heure_ouverture_matin=dtime(8, 0), heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 0), heure_fermeture_apres_midi=dtime(17, 0),
        )
        self.employe_a = Employe.objects.create(
            nom="Autorisé", prenom="A", matricule="EMPA",
            qr_code_token="11111111-1111-1111-1111-111111111111", actif=True,
        )
        self.employe_b = Employe.objects.create(
            nom="Victime", prenom="B", matricule="EMPB",
            qr_code_token="22222222-2222-2222-2222-222222222222", actif=True,
        )
        Pointage.objects.create(
            employe=self.employe_a, site=self.site, date_pointage=date.today(),
            periode='matin', type_journee='normal', heure_arrivee=dtime(8, 5),
        )
        Pointage.objects.create(
            employe=self.employe_b, site=self.site, date_pointage=date.today(),
            periode='matin', type_journee='normal', heure_arrivee=dtime(8, 32),
        )
        self.scanner_user = User.objects.create_user(username='scanner_hist_test', password='x')
        self.token = Token.objects.create(user=self.scanner_user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

    # CAS 1 : token scanner valide + historique de l'employé légitimement scanné -> succès
    def test_cas1_historique_de_lemploye_scanne_reussit(self):
        qr = f'EMPLOYE:{self.employe_a.matricule}:{self.employe_a.qr_code_token}'
        response = self.client.get('/api/mobile/pointages/', {'employee_qr': qr})
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert len(data['data']['pointages']) == 1

    # CAS 2 : token scanner valide + matricule seul d'un AUTRE employé -> refusé
    # (l'ancien mode "matricule seul" est purement et simplement retiré)
    def test_cas2_matricule_seul_dun_autre_employe_est_refuse(self):
        response = self.client.get('/api/mobile/pointages/', {'matricule': self.employe_b.matricule})
        assert response.status_code == 400  # employee_qr requis, matricule seul n'est plus un mode valide
        assert 'employee_qr' in response.json()['message']

    # CAS 3 : tentative de contournement — matricule de B avec le token de A -> refusé
    def test_cas3_matricule_et_token_incoherents_sont_refuses(self):
        qr_frauduleux = f'EMPLOYE:{self.employe_b.matricule}:{self.employe_a.qr_code_token}'
        response = self.client.get('/api/mobile/pointages/', {'employee_qr': qr_frauduleux})
        assert response.status_code == 404
        assert response.json()['status'] == 'error'
        # Vérifier qu'aucune donnée de B n'a fuité dans la réponse
        assert 'pointages' not in response.json()

    # CAS 4 : QR invalide -> 400 propre, jamais 500
    def test_cas4_qr_invalide_retourne_400(self):
        response = self.client.get('/api/mobile/pointages/', {'employee_qr': 'CECI_NEST_PAS_UN_QR_VALIDE'})
        assert response.status_code == 400
        assert response.json()['status'] == 'error'

    def test_cas4bis_uuid_invalide_retourne_400_pas_500(self):
        response = self.client.get('/api/mobile/pointages/', {
            'employee_qr': f'EMPLOYE:{self.employe_a.matricule}:pas-un-uuid'
        })
        assert response.status_code == 400

    # CAS 5 : employé inexistant -> réponse propre, jamais 500
    def test_cas5_employe_inexistant_retourne_404_propre(self):
        qr = 'EMPLOYE:INCONNU999:33333333-3333-3333-3333-333333333333'
        response = self.client.get('/api/mobile/pointages/', {'employee_qr': qr})
        assert response.status_code == 404
        assert response.json()['status'] == 'error'

    # CAS 6 : fonctionnement normal tel qu'utilisé par l'app -> succès
    def test_cas6_fonctionnement_normal_avec_date_optionnelle(self):
        qr = f'EMPLOYE:{self.employe_a.matricule}:{self.employe_a.qr_code_token}'
        response = self.client.get('/api/mobile/pointages/', {
            'employee_qr': qr, 'date': date.today().isoformat(),
        })
        assert response.status_code == 200
        assert response.json()['data']['employe']['matricule'] == self.employe_a.matricule

    def test_sans_token_dappareil_est_deja_bloque_en_amont(self):
        """Rappel : même avec un employee_qr parfaitement valide, l'absence
        de jeton d'appareil bloque tout (défense en profondeur)."""
        qr = f'EMPLOYE:{self.employe_a.matricule}:{self.employe_a.qr_code_token}'
        client_sans_token = APIClient()
        response = client_sans_token.get('/api/mobile/pointages/', {'employee_qr': qr})
        assert response.status_code == 401
