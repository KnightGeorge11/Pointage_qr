# Vérifie le contrat actuel de l'API Pointage : les écritures de présence
# passent par le moteur central process_scan() via le flux de scan QR.
# POST /api/pointages/ est volontairement interdit afin d'empêcher une
# création directe de présence hors contrôle du scanner.

from datetime import time as dtime, date
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase, Client
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from pointage.models import CustomUser, Employe, Site, Pointage, Scan
from pointage.services import process_scan


def _aware(date_, hh, mm):
    return timezone.make_aware(timezone.datetime.combine(date_, dtime(hh, mm)))


class PointageSerializerProcessScanTestCase(TestCase):
    def setUp(self):
        self.site = Site.objects.create(
            nom="Site API", adresse="1 Rue Test",
            heure_ouverture_matin=dtime(8, 0), heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 0), heure_fermeture_apres_midi=dtime(17, 0),
        )
        self.employe = Employe.objects.create(
            nom="Test", prenom="Api", matricule="APIT01",
            qr_code_token="22222222-2222-2222-2222-222222222222", actif=True,
        )
        self.admin = CustomUser.objects.create_user(
            username="admin_api", password="pass1234", role="admin", is_staff=True,
        )
        self.operateur = CustomUser.objects.create_user(
            username="operateur_api", password="pass1234", role="user",
        )
        token = Token.objects.create(user=self.operateur)
        self.mobile_client = APIClient()
        self.mobile_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        self.admin_client = Client()
        self.admin_client.force_login(self.admin)

    def _post_mobile_scan(self, employe=None, mode="auto", force_new=False, when=None):
        employe = employe or self.employe
        when = when or _aware(date(2026, 8, 10), 8, 0)
        payload = {
            "employee_qr": f"EMPLOYE:{employe.matricule}:{employe.qr_code_token}",
            "site_id": self.site.id,
            "mode": mode,
            "force_new": force_new,
        }
        with patch("pointage.services.timezone.now", return_value=when):
            return self.mobile_client.post("/api/mobile/scan/record/", payload, format="json")

    def test_creation_directe_pointage_api_est_interdite(self):
        response = self.admin_client.post(
            "/api/pointages/", {"employe": self.employe.id, "site": self.site.id}
        )
        assert response.status_code == 405
        assert not Pointage.objects.filter(employe=self.employe).exists()

    def test_scan_mobile_cree_une_entree_via_process_scan(self):
        response = self._post_mobile_scan()
        assert response.status_code == 201, response.content
        pointage = Pointage.objects.get(employe=self.employe, periode="matin")
        assert pointage.heure_arrivee == dtime(8, 0)
        assert pointage.type_journee == "normal"
        assert Scan.objects.filter(employe=self.employe, type_scan="entree_matin").exists()

    def test_sequence_normale_via_scan_mobile(self):
        jour = date(2026, 8, 10)
        for hh, mm in ((8, 0), (12, 0), (13, 0), (17, 0)):
            response = self._post_mobile_scan(when=_aware(jour, hh, mm))
            assert response.status_code == 201, response.content

        matin = Pointage.objects.get(employe=self.employe, periode="matin")
        apres_midi = Pointage.objects.get(employe=self.employe, periode="apres_midi")
        assert (matin.heure_arrivee, matin.heure_depart) == (dtime(8, 0), dtime(12, 0))
        assert (apres_midi.heure_arrivee, apres_midi.heure_depart) == (dtime(13, 0), dtime(17, 0))

    def test_garde_via_scan_mobile(self):
        jour = date(2026, 8, 10)
        Pointage.objects.create(
            employe=self.employe, site=self.site, date_pointage=jour,
            periode="nuit", type_journee="garde", statut="absent",
        )
        debut = self._post_mobile_scan(mode="garde", when=_aware(jour, 20, 0))
        fin = self._post_mobile_scan(mode="garde", when=_aware(date(2026, 8, 11), 6, 0))
        assert debut.status_code == 201, debut.content
        assert fin.status_code == 201, fin.content
        pointage = Pointage.objects.get(employe=self.employe, periode="nuit")
        assert pointage.heure_arrivee == dtime(20, 0)
        assert pointage.heure_depart == dtime(6, 0)
        assert pointage.date_depart == date(2026, 8, 11)

    def test_force_new_refuse_une_garde_anterieure_ouverte(self):
        ancienne = date(2026, 8, 8)
        Pointage.objects.create(
            employe=self.employe, site=self.site, date_pointage=ancienne,
            periode="nuit", type_journee="garde", statut="absent",
        )
        self._post_mobile_scan(mode="garde", when=_aware(ancienne, 20, 0))

        response = self._post_mobile_scan(
            mode="garde", force_new=True, when=_aware(date(2026, 8, 10), 20, 0)
        )
        assert response.status_code == 400, response.content
        assert response.json()["code"] == "GARDE_PRECEDENTE_NON_CLOTUREE"

    def test_double_scan_mobile_est_refuse(self):
        when = _aware(date(2026, 8, 10), 8, 0)
        first = self._post_mobile_scan(when=when)
        second = self._post_mobile_scan(when=when)
        assert first.status_code == 201
        assert second.status_code == 400
        assert second.json()["code"] == "DOUBLON"
        assert Pointage.objects.filter(employe=self.employe).count() == 1
        assert Scan.objects.filter(employe=self.employe).count() == 1

    def test_meme_decision_process_scan_et_mobile(self):
        when = _aware(date(2026, 8, 10), 8, 0)
        direct = process_scan(
            matricule=self.employe.matricule,
            qr_token=str(self.employe.qr_code_token),
            site_id=self.site.id,
            captured_at=when,
            client_event_id=uuid4(),
        )
        assert direct["status"] == "success"
        assert direct["code"] == "entree_matin"
