# pointage/tests/test_pointage_permissions.py
#
# role='user' ne doit jamais pouvoir créer/modifier/supprimer un
# Pointage, ni via l'interface web, ni via l'API REST. Seul l'Admin/RH
# (is_staff) le peut. Ce test ne touche pas à DemandeModification (qui
# reste réservé à Employé/Site/Poste, inchangé).
#
# Codes HTTP attendus, vérifiés empiriquement contre la config réelle du
# projet (REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES =
# [SessionAuthentication, TokenAuthentication]) :
#   - anonyme (aucun authenticator ne réussit) -> 403 (PermissionDenied),
#     PAS 401 : avec SessionAuthentication comme premier authenticator,
#     DRF ne renvoie 401 que si un authenticator actif fournit un
#     WWW-Authenticate header (ex: BasicAuthentication) — ce n'est pas
#     le cas ici, donc c'est bien 403 dans les deux cas (non authentifié
#     ET authentifié-mais-pas-permission). Confirmé par exécution directe
#     contre le projet.

from datetime import time as dtime, date

from django.test import TestCase, Client
from django.urls import reverse

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
        self.employe = Employe.objects.create(nom="Rakoto", prenom="Jean", matricule="E010", actif=True)
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
        assert self.utilisateur.is_staff is False

        client = Client()
        client.force_login(self.utilisateur)
        response = client.post(
            reverse('pointage_supprimer', args=[self.pointage.pk]), follow=True
        )

        assert Pointage.objects.filter(pk=self.pointage.pk).exists()
        assert response.status_code == 200  # redirigé avec succès, pas d'erreur serveur

    def test_anonyme_ne_peut_pas_supprimer_un_pointage(self):
        client = Client()
        response = client.post(reverse('pointage_supprimer', args=[self.pointage.pk]))
        assert Pointage.objects.filter(pk=self.pointage.pk).exists()
        assert response.status_code == 302  # redirigé vers le login (LoginRequiredMixin)

    def test_admin_peut_supprimer_un_pointage(self):
        client = Client()
        client.force_login(self.admin)
        client.post(reverse('pointage_supprimer', args=[self.pointage.pk]))
        assert not Pointage.objects.filter(pk=self.pointage.pk).exists()


class TestAPIPointagePermissions(PointagePermissionsTestCase):

    def test_utilisateur_peut_consulter_la_liste_via_api(self):
        client = Client()
        client.force_login(self.utilisateur)
        response = client.get('/api/pointages/')
        assert response.status_code == 200

    def test_utilisateur_peut_consulter_le_detail_via_api(self):
        client = Client()
        client.force_login(self.utilisateur)
        response = client.get(f'/api/pointages/{self.pointage.pk}/')
        assert response.status_code == 200

    def test_utilisateur_ne_peut_pas_creer_via_api(self):
        client = Client()
        client.force_login(self.utilisateur)
        count_avant = Pointage.objects.count()

        response = client.post('/api/pointages/', {
            'employe': self.employe.id, 'site': self.site.id,
            'date_pointage': date.today().isoformat(), 'periode': 'apres_midi',
            'type_journee': 'normal',
        })

        assert response.status_code == 403
        assert Pointage.objects.count() == count_avant

    def test_utilisateur_ne_peut_pas_modifier_via_api_patch(self):
        client = Client()
        client.force_login(self.utilisateur)

        response = client.patch(
            f'/api/pointages/{self.pointage.pk}/',
            data='{"heure_depart": "12:00:00"}',
            content_type='application/json',
        )

        assert response.status_code == 403
        self.pointage.refresh_from_db()
        assert self.pointage.heure_depart is None

    def test_utilisateur_ne_peut_pas_modifier_via_api_put(self):
        client = Client()
        client.force_login(self.utilisateur)

        response = client.put(
            f'/api/pointages/{self.pointage.pk}/',
            data='{"heure_depart": "12:00:00"}',
            content_type='application/json',
        )

        assert response.status_code == 403
        self.pointage.refresh_from_db()
        assert self.pointage.heure_depart is None

    def test_utilisateur_ne_peut_pas_supprimer_via_api(self):
        client = Client()
        client.force_login(self.utilisateur)

        response = client.delete(f'/api/pointages/{self.pointage.pk}/')

        assert response.status_code == 403
        assert Pointage.objects.filter(pk=self.pointage.pk).exists()

    def test_admin_peut_modifier_via_api(self):
        client = Client()
        client.force_login(self.admin)

        response = client.patch(
            f'/api/pointages/{self.pointage.pk}/',
            data='{"heure_depart": "12:00:00"}',
            content_type='application/json',
        )

        assert response.status_code == 200
        self.pointage.refresh_from_db()
        assert self.pointage.heure_depart == dtime(12, 0)

    def test_admin_peut_supprimer_via_api(self):
        client = Client()
        client.force_login(self.admin)

        response = client.delete(f'/api/pointages/{self.pointage.pk}/')

        assert response.status_code == 204
        assert not Pointage.objects.filter(pk=self.pointage.pk).exists()

    def test_anonyme_ne_peut_meme_pas_consulter(self):
        client = Client()
        response = client.get('/api/pointages/')
        assert response.status_code == 403

    def test_anonyme_ne_peut_pas_creer(self):
        client = Client()
        response = client.post('/api/pointages/', {
            'employe': self.employe.id, 'site': self.site.id,
            'date_pointage': date.today().isoformat(), 'periode': 'apres_midi',
        })
        assert response.status_code == 403
        assert Pointage.objects.count() == 1


class TestStatistiquesAction(PointagePermissionsTestCase):
    """statistiques doit être une vraie @action DRF (detail=False),
    routée par le DefaultRouter -> /api/pointages/statistiques/.
    Auparavant décorée avec @api_view sur une méthode de ViewSet, ce qui
    ne génère aucune URL exploitable (confirmé : 404 avant correction)."""

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
        client = Client()
        response = client.get('/api/pointages/statistiques/')
        assert response.status_code == 403


class TestAnomaliePermissionsAPI(PointagePermissionsTestCase):
    """Le traitement et la clôture d'une anomalie restent une capacité
    Admin/RH exclusive, y compris via l'API — pas seulement via l'admin
    Django."""

    def setUp(self):
        super().setUp()
        self.anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK, message="Scan pendant la pause",
            employe=self.employe, site=self.site, date_pointage=date.today(),
        )

    def test_utilisateur_peut_consulter_les_anomalies(self):
        client = Client()
        client.force_login(self.utilisateur)
        response = client.get('/api/anomalies/')
        assert response.status_code == 200

    def test_utilisateur_ne_peut_pas_traiter_une_anomalie_via_api(self):
        client = Client()
        client.force_login(self.utilisateur)

        response = client.post(
            f'/api/anomalies/{self.anomalie.pk}/traiter/',
            data='{"commentaire": "tentative non autorisée"}',
            content_type='application/json',
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
            data='{"commentaire": "vérifié, faux positif"}',
            content_type='application/json',
        )

        assert response.status_code == 200
        self.anomalie.refresh_from_db()
        assert self.anomalie.statut == AnomaliePointage.STATUT_TRAITEE

    def test_anonyme_ne_peut_pas_traiter_une_anomalie(self):
        client = Client()
        response = client.post(f'/api/anomalies/{self.anomalie.pk}/traiter/')
        assert response.status_code == 403


class TestProchainScanSortieMatinPrioritaire(PointagePermissionsTestCase):
    """Un employé n'ayant pas terminé son pointage du matin (entrée sans
    sortie) ne doit jamais se voir suggérer une entrée après-midi, même
    après 12h00 — c'est la sortie matin qui doit être indiquée en
    priorité, conformément à la règle missing_morning_exit du moteur."""

    def test_matin_incomplet_suggere_sortie_matin(self):
        # self.pointage (setUp) : matin, heure_arrivee=08:00, heure_depart=None
        client = Client()
        client.force_login(self.utilisateur)
        response = client.get(f'/api/prochain-scan/{self.employe.id}/')

        assert response.status_code == 200
        data = response.json()
        assert data['prochain_scan'] == 'sortie_matin'
        assert data['periode'] == 'matin'

    def test_matin_complet_suggere_entree_apres_midi(self):
        self.pointage.heure_depart = dtime(12, 0)
        self.pointage.save()

        client = Client()
        client.force_login(self.utilisateur)
        response = client.get(f'/api/prochain-scan/{self.employe.id}/')

        data = response.json()
        assert data['prochain_scan'] == 'entree_apres_midi'

    def test_apres_midi_incomplet_suggere_sortie_apres_midi(self):
        self.pointage.heure_depart = dtime(12, 0)
        self.pointage.save()
        Pointage.objects.create(
            employe=self.employe, site=self.site, date_pointage=date.today(),
            periode='apres_midi', type_journee='normal', heure_arrivee=dtime(13, 30),
        )

        client = Client()
        client.force_login(self.utilisateur)
        response = client.get(f'/api/prochain-scan/{self.employe.id}/')

        data = response.json()
        assert data['prochain_scan'] == 'sortie_apres_midi'

    def test_journee_complete(self):
        self.pointage.heure_depart = dtime(12, 0)
        self.pointage.save()
        Pointage.objects.create(
            employe=self.employe, site=self.site, date_pointage=date.today(),
            periode='apres_midi', type_journee='normal',
            heure_arrivee=dtime(13, 30), heure_depart=dtime(17, 30),
        )

        client = Client()
        client.force_login(self.utilisateur)
        response = client.get(f'/api/prochain-scan/{self.employe.id}/')

        data = response.json()
        assert data['prochain_scan'] is None
        assert data['type'] == 'complet'


class TestDemandeModificationInchange(TestCase):
    """Garde-fou : DemandeModification reste réservé à Employé/Site/Poste,
    'pointage' n'y a pas été ajouté."""

    def test_pointage_absent_des_cibles_de_demande(self):
        from pointage.models import DemandeModification
        cibles = [choice[0] for choice in DemandeModification.CIBLE_CHOICES]
        assert 'pointage' not in cibles
        assert set(cibles) == {'employe', 'site', 'poste'}
