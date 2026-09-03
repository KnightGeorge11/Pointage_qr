from datetime import date, time

from django.test import TestCase, Client

from pointage.models import CustomUser, Employe, Pointage, Poste, Site


class TestSensitiveAttendanceApis(TestCase):
    def setUp(self):
        self.rh = CustomUser.objects.create_user(
            username="rh_api_security", password="pass1234", role="admin", is_staff=True
        )
        self.user = CustomUser.objects.create_user(
            username="employee_api_security", password="pass1234", role="user", is_staff=False
        )
        self.poste = Poste.objects.create(nom="Test Security")
        self.site = Site.objects.create(
            nom="Site Security",
            adresse="Adresse",
            heure_ouverture_matin=time(8, 0),
            heure_fermeture_matin=time(12, 0),
            heure_ouverture_apres_midi=time(13, 0),
            heure_fermeture_apres_midi=time(17, 0),
        )
        self.employe = Employe.objects.create(
            nom="Rakoto",
            prenom="Jean",
            matricule="SEC001",
            poste=self.poste,
            email="jean@example.test",
            telephone="0340000000",
            actif=True,
        )
        Pointage.objects.create(
            employe=self.employe,
            site=self.site,
            date_pointage=date.today(),
            periode="matin",
            type_journee="normal",
            heure_arrivee=time(8, 0),
            heure_depart=time(12, 0),
        )

    def test_compte_normal_ne_peut_pas_lister_les_employes(self):
        client = Client()
        client.force_login(self.user)
        response = client.get("/api/employes/")
        self.assertEqual(response.status_code, 403)

    def test_compte_normal_ne_peut_pas_lister_les_pointages(self):
        client = Client()
        client.force_login(self.user)
        response = client.get("/api/pointages/")
        self.assertEqual(response.status_code, 403)

    def test_compte_normal_ne_peut_pas_recuperer_un_token_qr(self):
        client = Client()
        client.force_login(self.user)
        response = client.get(f"/api/employe-qr-data/{self.employe.matricule}/")
        self.assertEqual(response.status_code, 403)

    def test_compte_normal_ne_peut_pas_lire_le_statut_d_un_employe(self):
        client = Client()
        client.force_login(self.user)
        response = client.get(f"/api/statut-journee/{self.employe.id}/")
        self.assertEqual(response.status_code, 403)

    def test_rh_peut_lire_les_donnees_rh(self):
        client = Client()
        client.force_login(self.rh)
        self.assertEqual(client.get("/api/employes/").status_code, 200)
        self.assertEqual(client.get("/api/pointages/").status_code, 200)
        self.assertEqual(client.get(f"/api/employe-qr-data/{self.employe.matricule}/").status_code, 200)
        self.assertEqual(client.get(f"/api/statut-journee/{self.employe.id}/").status_code, 200)
        self.assertEqual(client.get("/api/dashboard-stats/").status_code, 200)
        self.assertEqual(client.get("/api/charts-data/").status_code, 200)
