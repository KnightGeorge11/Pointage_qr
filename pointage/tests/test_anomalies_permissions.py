from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from datetime import date
from pointage.models import AnomaliePointage, Employe, Site

User = get_user_model()


class AnomaliePermissionsTest(TestCase):
    """Tests de sécurité pour les anomalies de pointage."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin', password='admin123', is_staff=True, role='admin'
        )
        self.normal_user = User.objects.create_user(
            username='user', password='user123', role='user', is_staff=False
        )
        self.employe = Employe.objects.create(
            nom='Test', prenom='Test', matricule='TEST001'
        )
        self.site = Site.objects.create(
            nom='Site Test', adresse='123 Test Street',
            heure_ouverture_matin='08:00', heure_fermeture_matin='12:00',
            heure_ouverture_apres_midi='13:30', heure_fermeture_apres_midi='17:30'
        )
        self.anomalie = AnomaliePointage.objects.create(
            type='invalid_qr', message='Test anomalie', employe=self.employe,
            matricule_scanne='TEST001', site=self.site, date_pointage=date.today(),
            statut='ouverte'
        )
        self.client = Client()

    def test_normal_user_cannot_access_alertes_rh_view(self):
        """La page RH des anomalies est strictement réservée au RH."""
        self.client.login(username='user', password='user123')
        response = self.client.get(reverse('alertes_rh'))
        self.assertEqual(response.status_code, 403)

    def test_admin_user_can_access_alertes_rh_view(self):
        self.client.login(username='admin', password='admin123')
        response = self.client.get(reverse('alertes_rh'))
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_user_cannot_access_alertes_rh_view(self):
        response = self.client.get(reverse('alertes_rh'))
        self.assertEqual(response.status_code, 302)

    def test_normal_user_cannot_traiter_via_post(self):
        self.client.login(username='user', password='user123')
        response = self.client.post(reverse('alertes_rh'), {
            'anomalie_id': self.anomalie.id, 'action': 'traiter',
            'commentaire': 'Test de traitement'
        })
        self.assertEqual(response.status_code, 403)
        self.anomalie.refresh_from_db()
        self.assertEqual(self.anomalie.statut, 'ouverte')

    def test_admin_user_can_traiter_via_post(self):
        self.client.login(username='admin', password='admin123')
        response = self.client.post(reverse('alertes_rh'), {
            'anomalie_id': self.anomalie.id, 'action': 'traiter',
            'commentaire': 'Test de traitement'
        })
        self.assertEqual(response.status_code, 302)
        self.anomalie.refresh_from_db()
        self.assertEqual(self.anomalie.statut, 'traitee')

    def test_normal_user_cannot_cloturer_via_post(self):
        self.anomalie.statut = 'traitee'
        self.anomalie.save()
        self.client.login(username='user', password='user123')
        response = self.client.post(reverse('alertes_rh'), {
            'anomalie_id': self.anomalie.id, 'action': 'cloturer'
        })
        self.assertEqual(response.status_code, 403)
        self.anomalie.refresh_from_db()
        self.assertEqual(self.anomalie.statut, 'traitee')

    def test_admin_user_can_cloturer_via_post(self):
        self.anomalie.statut = 'traitee'
        self.anomalie.save()
        self.client.login(username='admin', password='admin123')
        response = self.client.post(reverse('alertes_rh'), {
            'anomalie_id': self.anomalie.id, 'action': 'cloturer'
        })
        self.assertEqual(response.status_code, 302)
        self.anomalie.refresh_from_db()
        self.assertEqual(self.anomalie.statut, 'cloturee')

    def test_normal_user_cannot_traiter_via_api(self):
        self.client.login(username='user', password='user123')
        url = reverse('anomalie-traiter', args=[self.anomalie.id])
        response = self.client.post(url, {'commentaire': 'Test API'})
        self.assertEqual(response.status_code, 403)

    def test_admin_user_can_traiter_via_api(self):
        self.client.login(username='admin', password='admin123')
        url = reverse('anomalie-traiter', args=[self.anomalie.id])
        response = self.client.post(url, {'commentaire': 'Test API'})
        self.assertEqual(response.status_code, 200)
        self.anomalie.refresh_from_db()
        self.assertEqual(self.anomalie.statut, 'traitee')

    def test_normal_user_cannot_cloturer_via_api(self):
        self.anomalie.statut = 'traitee'
        self.anomalie.save()
        self.client.login(username='user', password='user123')
        url = reverse('anomalie-cloturer', args=[self.anomalie.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_admin_user_can_cloturer_via_api(self):
        self.anomalie.statut = 'traitee'
        self.anomalie.save()
        self.client.login(username='admin', password='admin123')
        url = reverse('anomalie-cloturer', args=[self.anomalie.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.anomalie.refresh_from_db()
        self.assertEqual(self.anomalie.statut, 'cloturee')

    def test_unauthenticated_cannot_access_api(self):
        url = reverse('anomalie-traiter', args=[self.anomalie.id])
        response = self.client.post(url, {'commentaire': 'Test'})
        self.assertEqual(response.status_code, 403)

    def test_normal_user_cannot_view_anomalies_list(self):
        self.client.login(username='user', password='user123')
        response = self.client.get(reverse('anomalie-list'))
        self.assertEqual(response.status_code, 403)

    def test_admin_user_can_view_anomalies_list(self):
        self.client.login(username='admin', password='admin123')
        response = self.client.get(reverse('anomalie-list'))
        self.assertEqual(response.status_code, 200)

    def test_normal_user_cannot_view_anomalie_detail(self):
        self.client.login(username='user', password='user123')
        response = self.client.get(reverse('anomalie-detail', args=[self.anomalie.id]))
        self.assertEqual(response.status_code, 403)

    def test_marquer_traitee_raise_permission_error_for_normal_user(self):
        from pointage.anomalies import marquer_traitee
        with self.assertRaises(PermissionError):
            marquer_traitee(self.anomalie, self.normal_user)

    def test_marquer_traitee_accepts_admin_user(self):
        from pointage.anomalies import marquer_traitee
        traitement = marquer_traitee(
            self.anomalie, self.admin_user,
            commentaire='Traitement administratif de test',
        )
        self.assertIsNotNone(traitement)
        self.anomalie.refresh_from_db()
        self.assertEqual(self.anomalie.statut, 'traitee')

    def test_marquer_cloturee_raise_permission_error_for_normal_user(self):
        from pointage.anomalies import marquer_cloturee
        self.anomalie.statut = 'traitee'
        self.anomalie.save()
        with self.assertRaises(PermissionError):
            marquer_cloturee(self.anomalie, self.normal_user)

    def test_marquer_cloturee_accepts_admin_user(self):
        from pointage.anomalies import marquer_cloturee
        self.anomalie.statut = 'traitee'
        self.anomalie.save()
        result = marquer_cloturee(self.anomalie, self.admin_user)
        self.assertIsNotNone(result)
        self.anomalie.refresh_from_db()
        self.assertEqual(self.anomalie.statut, 'cloturee')
