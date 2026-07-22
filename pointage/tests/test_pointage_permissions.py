# pointage/tests/test_pointage_permissions.py
#
# role='user' ne doit jamais pouvoir créer/modifier/supprimer un
# Pointage, ni via l'interface web, ni via l'API REST. Seul l'Admin/RH
# (is_staff) le peut. Ce test ne touche pas à DemandeModification (qui
# reste réservé à Employé/Site/Poste, inchangé).

from datetime import time as dtime, date

from django.test import TestCase, Client
from django.urls import reverse

from pointage.models import CustomUser, Employe, Site, Pointage


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
        assert response.status_code == 302  # redirigé vers le login

    def test_admin_peut_supprimer_un_pointage(self):
        client = Client()
        client.force_login(self.admin)
        client.post(reverse('pointage_supprimer', args=[self.pointage.pk]))
        assert not Pointage.objects.filter(pk=self.pointage.pk).exists()


class TestAPIPointagePermissions(PointagePermissionsTestCase):

    def test_utilisateur_peut_consulter_via_api(self):
        client = Client()
        client.force_login(self.utilisateur)
        response = client.get('/api/pointages/')
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

        assert response.status_code in (401, 403)
        assert Pointage.objects.count() == count_avant

    def test_utilisateur_ne_peut_pas_modifier_via_api(self):
        client = Client()
        client.force_login(self.utilisateur)

        response = client.patch(
            f'/api/pointages/{self.pointage.pk}/',
            data='{"heure_depart": "12:00:00"}',
            content_type='application/json',
        )

        assert response.status_code in (401, 403)
        self.pointage.refresh_from_db()
        assert self.pointage.heure_depart is None

    def test_utilisateur_ne_peut_pas_supprimer_via_api(self):
        client = Client()
        client.force_login(self.utilisateur)

        response = client.delete(f'/api/pointages/{self.pointage.pk}/')

        assert response.status_code in (401, 403)
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

    def test_anonyme_ne_peut_meme_pas_consulter(self):
        client = Client()
        response = client.get('/api/pointages/')
        assert response.status_code in (401, 403)


class TestDemandeModificationInchange(TestCase):
    """Garde-fou : DemandeModification reste réservé à Employé/Site/Poste,
    'pointage' n'y a pas été ajouté."""

    def test_pointage_absent_des_cibles_de_demande(self):
        from pointage.models import DemandeModification
        cibles = [choice[0] for choice in DemandeModification.CIBLE_CHOICES]
        assert 'pointage' not in cibles
        assert set(cibles) == {'employe', 'site', 'poste'}
