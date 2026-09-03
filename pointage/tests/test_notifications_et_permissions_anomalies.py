# Tests de sécurité et de cohérence des notifications RH.
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pointage.models import AnomaliePointage, DemandeModification, Employe, Poste
from pointage.anomalies import enregistrer_anomalie

User = get_user_model()


class AccesAnomaliesUtilisateurNormalTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='employe_rh', password='motdepasse123', role='user'
        )
        self.admin = User.objects.create_user(
            username='admin_rh2', password='motdepasse123', role='admin', is_staff=True,
        )

    def test_utilisateur_normal_ne_peut_pas_voir_la_liste_des_anomalies(self):
        self.client.force_login(self.user)
        enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK,
            message="Scan pendant la pause", date_pointage=date.today(),
        )
        response = self.client.get(reverse('alertes_rh'))
        assert response.status_code == 403

    def test_utilisateur_normal_ne_peut_pas_traiter_une_anomalie(self):
        self.client.force_login(self.user)
        anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK,
            message="Scan pendant la pause", date_pointage=date.today(),
        )
        response = self.client.post(reverse('alertes_rh'), {
            'anomalie_id': anomalie.pk, 'action': 'cloturer',
        })
        anomalie.refresh_from_db()
        assert anomalie.statut == AnomaliePointage.STATUT_OUVERTE
        assert response.status_code == 403

    def test_admin_peut_toujours_traiter_une_anomalie(self):
        self.client.force_login(self.admin)
        anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK,
            message="Scan pendant la pause", date_pointage=date.today(),
        )
        self.client.post(reverse('alertes_rh'), {
            'anomalie_id': anomalie.pk, 'action': 'traiter', 'commentaire': 'Justifié.',
        })
        anomalie.refresh_from_db()
        assert anomalie.statut == AnomaliePointage.STATUT_TRAITEE


class NotificationsApiTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='employe_notif', password='motdepasse123', role='user'
        )
        self.admin = User.objects.create_user(
            username='admin_notif', password='motdepasse123', role='admin', is_staff=True,
        )

    def test_anomalie_ouverte_non_visible_pour_utilisateur_normal(self):
        enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK,
            message="Scan pendant la pause", date_pointage=date.today(),
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse('notifications_api'))
        assert response.status_code == 200
        data = response.json()
        assert not any(n['type'] == 'anomalie' for n in data['notifications'])

    def test_anomalie_ouverte_visible_pour_admin(self):
        enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK,
            message="Scan pendant la pause", date_pointage=date.today(),
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse('notifications_api'))
        data = response.json()
        assert any(n['type'] == 'anomalie' for n in data['notifications'])

    def test_anomalie_cloturee_absente_des_notifications(self):
        anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK,
            message="Scan pendant la pause", date_pointage=date.today(),
        )
        anomalie.statut = AnomaliePointage.STATUT_CLOTUREE
        anomalie.save()
        self.client.force_login(self.admin)
        response = self.client.get(reverse('notifications_api'))
        data = response.json()
        assert not any(n['type'] == 'anomalie' for n in data['notifications'])

    def test_admin_voit_les_demandes_en_attente(self):
        DemandeModification.objects.create(
            demandeur=self.user, type_action='update', cible='employe',
            donnees={}, statut='en_attente',
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse('notifications_api'))
        data = response.json()
        assert any(n['type'] == 'demande_en_attente' for n in data['notifications'])

    def test_utilisateur_voit_ses_propres_demandes_traitees(self):
        DemandeModification.objects.create(
            demandeur=self.user, type_action='update', cible='employe',
            donnees={}, statut='approuvee', traitee_par=self.admin,
            date_traitement=timezone.now(),
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse('notifications_api'))
        data = response.json()
        assert any(n['type'] == 'demande_traitee' for n in data['notifications'])

    def test_utilisateur_ne_voit_pas_les_demandes_en_attente_dautres_personnes(self):
        DemandeModification.objects.create(
            demandeur=self.admin, type_action='update', cible='employe',
            donnees={}, statut='en_attente',
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse('notifications_api'))
        data = response.json()
        assert not any(n['type'] == 'demande_en_attente' for n in data['notifications'])


class DonneesFormateesAdminTestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='super_donnees', password='motdepasse123', email='a@a.com',
        )
        self.user = User.objects.create_user(
            username='demandeur', password='motdepasse123', role='user'
        )
        self.client.force_login(self.admin)
        self.poste1 = Poste.objects.create(nom="Infirmier")
        self.poste2 = Poste.objects.create(nom="Médecin")
        self.employe = Employe.objects.create(
            nom="Rakoto", prenom="Jean", matricule="ORIG01", actif=True, poste=self.poste1,
        )

    def test_update_affiche_avant_et_apres(self):
        demande = DemandeModification.objects.create(
            demandeur=self.user, type_action='update', cible='employe',
            cible_id=self.employe.pk,
            donnees={
                'nom': 'Rakoto', 'prenom': 'Jean', 'matricule': 'MODIFIE01',
                'poste': self.poste2.pk, 'actif': 'True',
            },
        )
        response = self.client.get(
            f'/admin/pointage/demandemodification/{demande.pk}/change/'
        )
        content = response.content.decode()
        assert response.status_code == 200
        assert 'ORIG01' in content
        assert 'MODIFIE01' in content
        assert 'Infirmier' in content
        assert 'Médecin' in content

    def test_create_naffiche_pas_de_colonne_avant(self):
        demande = DemandeModification.objects.create(
            demandeur=self.user, type_action='create', cible='employe', cible_id=None,
            donnees={'nom': 'Rabe', 'prenom': 'Marie', 'matricule': 'NEW01',
                     'poste': self.poste1.pk, 'actif': 'True'},
        )
        response = self.client.get(
            f'/admin/pointage/demandemodification/{demande.pk}/change/'
        )
        assert response.status_code == 200
        assert 'NEW01' in response.content.decode()

    def test_delete_affiche_les_valeurs_actuelles_de_lelement(self):
        demande = DemandeModification.objects.create(
            demandeur=self.user, type_action='delete', cible='employe',
            cible_id=self.employe.pk, donnees={},
        )
        response = self.client.get(
            f'/admin/pointage/demandemodification/{demande.pk}/change/'
        )
        content = response.content.decode()
        assert response.status_code == 200
        assert 'ORIG01' in content
        assert 'supprim' in content.lower()

    def test_element_cible_deja_supprime_naffiche_pas_derreur(self):
        demande = DemandeModification.objects.create(
            demandeur=self.user, type_action='update', cible='employe',
            cible_id=999999,
            donnees={'nom': 'X', 'prenom': 'Y', 'matricule': 'Z',
                     'poste': None, 'actif': 'True'},
        )
        response = self.client.get(
            f'/admin/pointage/demandemodification/{demande.pk}/change/'
        )
        assert response.status_code == 200
