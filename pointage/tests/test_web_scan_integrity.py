from datetime import time

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from pointage.models import CustomUser, Employe, Pointage, Poste, Site
from pointage.views import get_statut_employe_journee


class WebScanIntegrityTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="web_integrity_user",
            password="pass1234",
            role="user",
        )
        self.poste = Poste.objects.create(nom="Web integrity")
        self.site = Site.objects.create(
            nom="Site Web Integrity",
            adresse="Adresse",
            heure_ouverture_matin=time(8, 0),
            heure_fermeture_matin=time(12, 0),
            heure_ouverture_apres_midi=time(13, 0),
            heure_fermeture_apres_midi=time(17, 0),
        )
        self.employe = Employe.objects.create(
            nom="Test",
            prenom="Badge",
            matricule="WEB001",
            poste=self.poste,
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_matricule_seul_est_refuse_par_le_scanner_web(self):
        response = self.client.post(
            reverse("scanner"),
            {
                "matricule": self.employe.matricule,
                "site_id": self.site.id,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            Pointage.objects.filter(employe=self.employe).exists()
        )

    def test_qr_valide_reste_accepte_par_le_scanner_web(self):
        qr = f"EMPLOYE:{self.employe.matricule}:{self.employe.qr_code_token}"
        response = self.client.post(
            reverse("scanner"),
            {
                "qr_data": qr,
                "site_id": self.site.id,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Pointage.objects.filter(
                employe=self.employe,
                heure_arrivee__isnull=False,
            ).exists()
        )

    def test_garde_planifiee_sans_arrivee_n_est_pas_une_presence(self):
        today = timezone.localtime(timezone.now()).date()
        Pointage.objects.create(
            employe=self.employe,
            site=self.site,
            date_pointage=today,
            periode="nuit",
            type_journee="garde",
            heure_arrivee=None,
            heure_depart=None,
        )

        statut = get_statut_employe_journee(self.employe, today)

        self.assertFalse(statut["nuit"]["present"])
