from datetime import date, time

from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from pointage.models import CustomUser, Employe, Pointage, Poste, Site


class CriticalAttendanceAuditTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="audit_user", password="pass1234", role="user"
        )
        self.rh = CustomUser.objects.create_user(
            username="audit_rh", password="pass1234", role="admin", is_staff=True
        )
        self.poste = Poste.objects.create(nom="Audit")
        self.site = Site.objects.create(
            nom="Site Audit",
            adresse="Adresse",
            heure_ouverture_matin=time(8, 0),
            heure_fermeture_matin=time(12, 0),
            heure_ouverture_apres_midi=time(13, 0),
            heure_fermeture_apres_midi=time(17, 0),
        )
        self.employe = Employe.objects.create(
            nom="Test", prenom="Audit", matricule="AUD001", poste=self.poste
        )

    def test_scanner_web_refuse_un_matricule_sans_qr(self):
        client = Client()
        client.force_login(self.user)
        response = client.post(
            reverse("scanner"),
            {"matricule": self.employe.matricule, "site_id": self.site.id},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Pointage.objects.filter(employe=self.employe).exists())

    def test_garde_planifiee_ne_compte_pas_comme_presence(self):
        today = date.today()
        Pointage.objects.create(
            employe=self.employe,
            site=self.site,
            date_pointage=today,
            periode="nuit",
            type_journee="garde",
            heure_arrivee=None,
            heure_depart=None,
        )

        client = Client()
        client.force_login(self.rh)
        response = client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["presents_aujourdhui"], 0)
        self.assertEqual(response.context["absents_aujourdhui"], 1)

    def test_presence_est_comptee_apres_une_vraie_entree(self):
        Pointage.objects.create(
            employe=self.employe,
            site=self.site,
            date_pointage=date.today(),
            periode="matin",
            type_journee="normal",
            heure_arrivee=time(8, 5),
        )

        client = Client()
        client.force_login(self.rh)
        response = client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["presents_aujourdhui"], 1)
        self.assertEqual(response.context["absents_aujourdhui"], 0)

    def test_api_pointage_ne_permet_pas_creation_directe(self):
        client = APIClient()
        client.force_authenticate(user=self.rh)
        response = client.post("/api/pointages/", {})
        self.assertEqual(response.status_code, 405)

    def test_api_pointage_ne_permet_pas_modification_directe(self):
        pointage = Pointage.objects.create(
            employe=self.employe,
            site=self.site,
            date_pointage=date.today(),
            periode="matin",
            type_journee="normal",
            heure_arrivee=time(8, 0),
        )
        client = APIClient()
        client.force_authenticate(user=self.rh)
        response = client.patch(
            f"/api/pointages/{pointage.id}/",
            {"heure_arrivee": "09:00:00"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        pointage.refresh_from_db()
        self.assertEqual(pointage.heure_arrivee, time(8, 0))
