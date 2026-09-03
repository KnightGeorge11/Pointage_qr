from datetime import time as dtime, date, datetime
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from pointage.models import CustomUser, Employe, Site, Pointage, AnomaliePointage
from pointage.anomalies import enregistrer_anomalie


class PointagePermissionsTestCase(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username="admin_perm", password="pass1234", role="admin", is_staff=True,
        )
        self.utilisateur = CustomUser.objects.create_user(
            username="user_perm", password="pass1234", role="user",
        )
        self.employe = Employe.objects.create(
            nom="Rakoto", prenom="Jean", matricule="E010", actif=True
        )
        self.site = Site.objects.create(
            nom="Site", adresse="a",
            heure_ouverture_matin=dtime(8, 0), heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 30), heure_fermeture_apres_midi=dtime(17, 30),
        )
        self.pointage = Pointage.objects.create(
            employe=self.employe, site=self.site, date_pointage=date.today(),
            periode='matin', type_journee='normal', heure_arrivee=dtime(8, 0),
        )


class TestSuppressionWebPointage(PointagePermissionsTestCase):
    def test_utilisateur_ne_peut_pas_supprimer_un_pointage(self):
        client = Client()
        client.force_login(self.utilisateur)
        response = client.post(reverse('pointage_supprimer', args=[self.pointage.pk]), follow=True)
        assert Pointage.objects.filter(pk=self.pointage.pk).exists()
        assert response.status_code == 403

    def test_anonyme_ne_peut_pas_supprimer_un_pointage(self):
        response = Client().post(reverse('pointage_supprimer', args=[self.pointage.pk]))
        assert Pointage.objects.filter(pk=self.pointage.pk).exists()
        # L'endpoint de suppression est protégé par login_required : un anonyme
        # est redirigé vers la page de connexion, sans mutation de la donnée.
        assert response.status_code == 302

    def test_admin_ne_peut_pas_supprimer_un_pointage(self):
        client = Client()
        client.force_login(self.admin)
        response = client.post(reverse('pointage_supprimer', args=[self.pointage.pk]))
        assert Pointage.objects.filter(pk=self.pointage.pk).exists()
        assert response.status_code == 403


class TestAPIPointagePermissions(PointagePermissionsTestCase):
    def test_utilisateur_peut_consulter_la_liste_via_api(self):
        response = self._client().get('/api/pointages/')
        assert response.status_code == 200

    def test_utilisateur_peut_consulter_le_detail_via_api(self):
        response = self._client().get(f'/api/pointages/{self.pointage.pk}/')
        assert response.status_code == 200

    def _client(self):
        client = Client()
        client.force_login(self.utilisateur)
        return client

    def test_utilisateur_ne_peut_pas_creer_via_api(self):
        count_avant = Pointage.objects.count()
        response = self._client().post('/api/pointages/', {
            'employe': self.employe.id, 'site': self.site.id,
            'date_pointage': date.today().isoformat(), 'periode': 'apres_midi',
            'type_journee': 'normal',
        })
        assert response.status_code == 403
        assert Pointage.objects.count() == count_avant

    def test_utilisateur_ne_peut_pas_modifier_via_api_patch(self):
        response = self._client().patch(
            f'/api/pointages/{self.pointage.pk}/',
            data='{"heure_depart": "12:00:00"}', content_type='application/json',
        )
        assert response.status_code == 403
        self.pointage.refresh_from_db()
        assert self.pointage.heure_depart is None

    def test_utilisateur_ne_peut_pas_modifier_via_api_put(self):
        response = self._client().put(
            f'/api/pointages/{self.pointage.pk}/',
            data='{"heure_depart": "12:00:00"}', content_type='application/json',
        )
        assert response.status_code == 403
        self.pointage.refresh_from_db()
        assert self.pointage.heure_depart is None

    def test_utilisateur_ne_peut_pas_supprimer_via_api(self):
        response = self._client().delete(f'/api/pointages/{self.pointage.pk}/')
        assert response.status_code == 403
        assert Pointage.objects.filter(pk=self.pointage.pk).exists()
