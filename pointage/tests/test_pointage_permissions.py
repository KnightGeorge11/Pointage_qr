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

    def test_admin_peut_modifier_via_api(self):
        client = Client()
        client.force_login(self.admin)
        response = client.patch(
            f'/api/pointages/{self.pointage.pk}/',
            data='{"heure_depart": "12:00:00"}', content_type='application/json',
        )
        assert response.status_code == 200
        self.pointage.refresh_from_db()
        assert self.pointage.heure_depart == dtime(12, 0)

    def test_admin_ne_peut_pas_supprimer_via_api(self):
        client = Client()
        client.force_login(self.admin)
        response = client.delete(f'/api/pointages/{self.pointage.pk}/')
        assert response.status_code == 403
        assert Pointage.objects.filter(pk=self.pointage.pk).exists()

    def test_anonyme_ne_peut_meme_pas_consulter(self):
        response = Client().get('/api/pointages/')
        assert response.status_code == 403

    def test_anonyme_ne_peut_pas_creer(self):
        response = Client().post('/api/pointages/', {
            'employe': self.employe.id, 'site': self.site.id,
            'date_pointage': date.today().isoformat(), 'periode': 'apres_midi',
        })
        assert response.status_code == 403
        assert Pointage.objects.count() == 1


class TestStatistiquesAction(PointagePermissionsTestCase):
    def test_endpoint_statistiques_existe_et_repond(self):
        client = Client()
        client.force_login(self.utilisateur)
        response = client.get('/api/pointages/statistiques/')
        assert response.status_code == 200
        data = response.json()
        assert 'presents_aujourdhui' in data
        assert 'total_employes' in data
        assert 'gardes_en_cours' in data

    def test_statistiques_refuse_anonyme(self):
        assert Client().get('/api/pointages/statistiques/').status_code == 403


class TestAnomaliePermissionsAPI(PointagePermissionsTestCase):
    def setUp(self):
        super().setUp()
        self.anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK, message="Scan pendant la pause",
            employe=self.employe, site=self.site, date_pointage=date.today(),
        )

    def test_utilisateur_ne_peut_pas_consulter_les_anomalies(self):
        client = Client()
        client.force_login(self.utilisateur)
        response = client.get('/api/anomalies/')
        assert response.status_code == 403

    def test_utilisateur_ne_peut_pas_traiter_une_anomalie_via_api(self):
        client = Client()
        client.force_login(self.utilisateur)
        response = client.post(
            f'/api/anomalies/{self.anomalie.pk}/traiter/',
            data='{"commentaire": "tentative non autorisée"}', content_type='application/json',
        )
        assert response.status_code == 403
        self.anomalie.refresh_from_db()
        assert self.anomalie.statut == AnomaliePointage.STATUT_OUVERTE

    def test_utilisateur_ne_peut_pas_cloturer_une_anomalie_via_api(self):
        client = Client()
        client.force_login(self.utilisateur)
        response = client.post(f'/api/anomalies/{self.anomalie.pk}/cloturer/')
        assert response.status_code == 403
        self.anomalie.refresh_from_db()
        assert self.anomalie.statut == AnomaliePointage.STATUT_OUVERTE

    def test_admin_peut_traiter_une_anomalie_via_api(self):
        client = Client()
        client.force_login(self.admin)
        response = client.post(
            f'/api/anomalies/{self.anomalie.pk}/traiter/',
            data='{"commentaire": "vérifié, faux positif"}', content_type='application/json',
        )
        assert response.status_code == 200
        self.anomalie.refresh_from_db()
        assert self.anomalie.statut == AnomaliePointage.STATUT_TRAITEE

    def test_anonyme_ne_peut_pas_traiter_une_anomalie(self):
        assert Client().post(f'/api/anomalies/{self.anomalie.pk}/traiter/').status_code == 403


class TestProchainScanSortieMatinPrioritaire(PointagePermissionsTestCase):
    def test_matin_incomplet_suggere_sortie_matin(self):
        fake_now = timezone.make_aware(datetime.combine(date.today(), dtime(9, 0)))
        client = Client()
        client.force_login(self.utilisateur)
        with patch('pointage.views.timezone.now', return_value=fake_now):
            response = client.get(f'/api/prochain-scan/{self.employe.id}/')
        assert response.status_code == 200
        data = response.json()
        assert data['prochain_scan'] == 'sortie_matin'
        assert data['periode'] == 'matin'

    def test_matin_complet_suggere_entree_apres_midi(self):
        self.pointage.heure_depart = dtime(12, 0)
        self.pointage.save()
        fake_now = timezone.make_aware(datetime.combine(date.today(), dtime(14, 0)))
        client = Client()
        client.force_login(self.utilisateur)
        with patch('pointage.views.timezone.now', return_value=fake_now):
            response = client.get(f'/api/prochain-scan/{self.employe.id}/')
        assert response.json()['prochain_scan'] == 'entree_apres_midi'

    def test_apres_midi_incomplet_suggere_sortie_apres_midi(self):
        self.pointage.heure_depart = dtime(12, 0)
        self.pointage.save()
        Pointage.objects.create(
            employe=self.employe, site=self.site, date_pointage=date.today(),
            periode='apres_midi', type_journee='normal', heure_arrivee=dtime(13, 30),
        )
        fake_now = timezone.make_aware(datetime.combine(date.today(), dtime(15, 0)))
        client = Client()
        client.force_login(self.utilisateur)
        with patch('pointage.views.timezone.now', return_value=fake_now):
            response = client.get(f'/api/prochain-scan/{self.employe.id}/')
        assert response.json()['prochain_scan'] == 'sortie_apres_midi'

    def test_journee_complete(self):
        self.pointage.heure_depart = dtime(12, 0)
        self.pointage.save()
        Pointage.objects.create(
            employe=self.employe, site=self.site, date_pointage=date.today(),
            periode='apres_midi', type_journee='normal',
            heure_arrivee=dtime(13, 30), heure_depart=dtime(17, 30),
        )
        fake_now = timezone.make_aware(datetime.combine(date.today(), dtime(18, 0)))
        client = Client()
        client.force_login(self.utilisateur)
        with patch('pointage.views.timezone.now', return_value=fake_now):
            response = client.get(f'/api/prochain-scan/{self.employe.id}/')
        data = response.json()
        assert data['prochain_scan'] is None
        assert data['type'] == 'complet'


class TestDemandeModificationInchange(TestCase):
    def test_pointage_absent_des_cibles_de_demande(self):
        from pointage.models import DemandeModification
        cibles = [choice[0] for choice in DemandeModification.CIBLE_CHOICES]
        assert 'pointage' not in cibles
        assert set(cibles) == {'employe', 'site', 'poste'}
