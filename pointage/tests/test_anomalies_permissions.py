from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from datetime import date
from pointage.models import AnomaliePointage, Employe, Site

User = get_user_model()


class AnomaliePermissionsTest(TestCase):
    """Tests de sécurité pour les anomalies de pointage."""

    def setUp(self):
        # Créer un admin (is_staff=True)
        self.admin_user = User.objects.create_user(
            username='admin',
            password='admin123',
            is_staff=True,
            role='admin'
        )
        # Créer un utilisateur normal (role='user')
        self.normal_user = User.objects.create_user(
            username='user',
            password='user123',
            role='user',
            is_staff=False
        )
        # Créer un employé pour les tests
        self.employe = Employe.objects.create(
            nom='Test',
            prenom='Test',
            matricule='TEST001'
        )
        # Créer un site
        self.site = Site.objects.create(
            nom='Site Test',
            adresse='123 Test Street',
            heure_ouverture_matin='08:00',
            heure_fermeture_matin='12:00',
            heure_ouverture_apres_midi='13:30',
            heure_fermeture_apres_midi='17:30'
        )
        # Créer une anomalie ouverte
        self.anomalie = AnomaliePointage.objects.create(
            type='invalid_qr',
            message='Test anomalie',
            employe=self.employe,
            matricule_scanne='TEST001',
            site=self.site,
            date_pointage=date.today(),
            statut='ouverte'
        )
        # Client HTTP
        self.client = Client()

    # ─── Tests d'accès à la vue web ─────────────────────────────────────

    def test_normal_user_can_access_alertes_rh_view(self):
        """
        Un utilisateur normal peut consulter la liste des anomalies (vue en
        lecture) — seul le TRAITEMENT (POST) reste réservé aux admins,
        vérifié séparément par test_normal_user_cannot_traiter_via_post.
        """
        self.client.login(username='user', password='user123')
        response = self.client.get(reverse('alertes_rh'))
        self.assertEqual(response.status_code, 200)

    def test_admin_user_can_access_alertes_rh_view(self):
        """Un admin peut accéder à la vue des anomalies."""
        self.client.login(username='admin', password='admin123')
        response = self.client.get(reverse('alertes_rh'))
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_user_cannot_access_alertes_rh_view(self):
        """Un utilisateur non authentifié ne peut pas accéder à la vue des anomalies."""
        response = self.client.get(reverse('alertes_rh'))
        self.assertEqual(response.status_code, 302)  # Redirection vers login

    # ─── Tests de traitement via POST web ───────────────────────────────

    def test_normal_user_cannot_traiter_via_post(self):
        """Un utilisateur normal ne peut pas traiter une anomalie via POST."""
        self.client.login(username='user', password='user123')
        response = self.client.post(reverse('alertes_rh'), {
            'anomalie_id': self.anomalie.id,
            'action': 'traiter',
            'commentaire': 'Test de traitement'
        })
        # 302 = redirection (staff_member_required)
        self.assertEqual(response.status_code, 302)

    def test_admin_user_can_traiter_via_post(self):
        """Un admin peut traiter une anomalie via POST."""
        self.client.login(username='admin', password='admin123')
        response = self.client.post(reverse('alertes_rh'), {
            'anomalie_id': self.anomalie.id,
            'action': 'traiter',
            'commentaire': 'Test de traitement'
        })
        self.assertEqual(response.status_code, 302)  # Redirection après traitement
        self.anomalie.refresh_from_db()
        self.assertEqual(self.anomalie.statut, 'traitee')

    def test_normal_user_cannot_cloturer_via_post(self):
        """Un utilisateur normal ne peut pas clôturer une anomalie via POST."""
        # Mettre l'anomalie en statut 'traitee' d'abord
        self.anomalie.statut = 'traitee'
        self.anomalie.save()

        self.client.login(username='user', password='user123')
        response = self.client.post(reverse('alertes_rh'), {
            'anomalie_id': self.anomalie.id,
            'action': 'cloturer'
        })
        self.assertEqual(response.status_code, 302)  # Redirection

    def test_admin_user_can_cloturer_via_post(self):
        """Un admin peut clôturer une anomalie via POST."""
        # Mettre l'anomalie en statut 'traitee' d'abord
        self.anomalie.statut = 'traitee'
        self.anomalie.save()

        self.client.login(username='admin', password='admin123')
        response = self.client.post(reverse('alertes_rh'), {
            'anomalie_id': self.anomalie.id,
            'action': 'cloturer'
        })
        self.assertEqual(response.status_code, 302)
        self.anomalie.refresh_from_db()
        self.assertEqual(self.anomalie.statut, 'cloturee')

    # ─── Tests d'accès à l'API ──────────────────────────────────────────

    def test_normal_user_cannot_traiter_via_api(self):
        """Un utilisateur normal ne peut pas traiter une anomalie via l'API."""
        self.client.login(username='user', password='user123')
        url = reverse('anomalie-traiter', args=[self.anomalie.id])
        response = self.client.post(url, {'commentaire': 'Test API'})
        self.assertEqual(response.status_code, 403)  # Forbidden

    def test_admin_user_can_traiter_via_api(self):
        """Un admin peut traiter une anomalie via l'API."""
        self.client.login(username='admin', password='admin123')
        url = reverse('anomalie-traiter', args=[self.anomalie.id])
        response = self.client.post(url, {'commentaire': 'Test API'})
        self.assertEqual(response.status_code, 200)
        self.anomalie.refresh_from_db()
        self.assertEqual(self.anomalie.statut, 'traitee')

    def test_normal_user_cannot_cloturer_via_api(self):
        """Un utilisateur normal ne peut pas clôturer une anomalie via l'API."""
        self.anomalie.statut = 'traitee'
        self.anomalie.save()

        self.client.login(username='user', password='user123')
        url = reverse('anomalie-cloturer', args=[self.anomalie.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)  # Forbidden

    def test_admin_user_can_cloturer_via_api(self):
        """Un admin peut clôturer une anomalie via l'API."""
        self.anomalie.statut = 'traitee'
        self.anomalie.save()

        self.client.login(username='admin', password='admin123')
        url = reverse('anomalie-cloturer', args=[self.anomalie.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.anomalie.refresh_from_db()
        self.assertEqual(self.anomalie.statut, 'cloturee')

    def test_unauthenticated_cannot_access_api(self):
        """Un utilisateur non authentifié ne peut pas accéder à l'API."""
        url = reverse('anomalie-traiter', args=[self.anomalie.id])
        response = self.client.post(url, {'commentaire': 'Test'})
        self.assertEqual(response.status_code, 403)  # DRF renvoie 403 pour non authentifié

    # ─── Tests de lecture (GET) ──────────────────────────────────────────

    def test_normal_user_can_view_anomalies_list(self):
        """Un utilisateur normal peut consulter la liste des anomalies (lecture seule)."""
        self.client.login(username='user', password='user123')
        url = reverse('anomalie-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_admin_user_can_view_anomalies_list(self):
        """Un admin peut consulter la liste des anomalies."""
        self.client.login(username='admin', password='admin123')
        url = reverse('anomalie-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_normal_user_can_view_anomalie_detail(self):
        """Un utilisateur normal peut consulter le détail d'une anomalie (lecture seule)."""
        self.client.login(username='user', password='user123')
        url = reverse('anomalie-detail', args=[self.anomalie.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # ─── Tests des fonctions métier ──────────────────────────────────────

    def test_marquer_traitee_raise_permission_error_for_normal_user(self):
        """marquer_traitee() lève PermissionError pour un utilisateur normal."""
        from pointage.anomalies import marquer_traitee
        with self.assertRaises(PermissionError):
            marquer_traitee(self.anomalie, self.normal_user)

    def test_marquer_traitee_accepts_admin_user(self):
        """marquer_traitee() accepte un utilisateur admin."""
        from pointage.anomalies import marquer_traitee
        traitement = marquer_traitee(self.anomalie, self.admin_user)
        self.assertIsNotNone(traitement)
        self.anomalie.refresh_from_db()
        self.assertEqual(self.anomalie.statut, 'traitee')

    def test_marquer_cloturee_raise_permission_error_for_normal_user(self):
        """marquer_cloturee() lève PermissionError pour un utilisateur normal."""
        from pointage.anomalies import marquer_cloturee
        self.anomalie.statut = 'traitee'
        self.anomalie.save()
        with self.assertRaises(PermissionError):
            marquer_cloturee(self.anomalie, self.normal_user)

    def test_marquer_cloturee_accepts_admin_user(self):
        """marquer_cloturee() accepte un utilisateur admin."""
        from pointage.anomalies import marquer_cloturee
        self.anomalie.statut = 'traitee'
        self.anomalie.save()
        result = marquer_cloturee(self.anomalie, self.admin_user)
        self.assertIsNotNone(result)
        self.anomalie.refresh_from_db()
        self.assertEqual(self.anomalie.statut, 'cloturee')