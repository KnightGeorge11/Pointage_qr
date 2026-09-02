# pointage/tests/test_pointage_serializer_process_scan.py
#
# PointageSerializer.create() (POST /api/pointages/) ne doit plus contenir
# de moteur de décision indépendant : il doit déléguer entièrement à
# process_scan() / DayStateMachine, exactement comme MobileRecordScanAPIView
# (POST /api/mobile/scan/record/) et ScanAPIView (scanner web). Ce fichier
# vérifie que les deux points d'entrée produisent le même résultat pour les
# mêmes scénarios, et que toutes les protections de process_scan() restent
# actives quand on passe par le serializer REST (anti-doublon, force_new,
# garde/minuit, employé invalide/inactif).

from datetime import time as dtime, date
from unittest.mock import patch

from django.test import TestCase, Client
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from pointage.models import CustomUser, Employe, Site, Pointage, Scan


def _aware(date_, hh, mm):
    return timezone.make_aware(timezone.datetime.combine(date_, dtime(hh, mm)))


class PointageSerializerProcessScanTestCase(TestCase):
    """Base commune : un site, un employé, un admin (pour /api/pointages/)
    et un opérateur avec token (pour /api/mobile/scan/record/)."""

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
        self.token = Token.objects.create(user=self.operateur)
        self.mobile_client = APIClient()
        self.mobile_client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.admin_client = Client()
        self.admin_client.force_login(self.admin)

    def _post_pointages_api(self, employe=None, site=None, extra=None):
        data = {"employe": (employe or self.employe).id, "site": (site or self.site).id}
        if extra:
            data.update(extra)
        return self.admin_client.post("/api/pointages/", data)

    def _post_mobile_scan(self, employe=None, site=None, mode="auto", force_new=False):
        employe = employe or self.employe
        site = site or self.site
        return self.mobile_client.post(
            "/api/mobile/scan/record/",
            {
                "employee_qr": f"EMPLOYE:{employe.matricule}:{employe.qr_code_token}",
                "site_id": site.id,
                "mode": mode,
                "force_new": force_new,
            },
            format="json",
        )


class TestParitePointageNormal(PointageSerializerProcessScanTestCase):
    """E1 -> S1 -> E2 -> S2 : les deux points d'entrée doivent produire
    exactement le même enchaînement d'états sur le même Pointage."""

    def test_entree_matin_via_api_pointages(self):
        now = _aware(date(2026, 8, 10), 8, 0)
        with patch("pointage.services.timezone.now", return_value=now):
            response = self._post_pointages_api()

        assert response.status_code == 201, response.content
        pointage = Pointage.objects.get(employe=self.employe, periode="matin")
        assert pointage.heure_arrivee == dtime(8, 0)
        assert pointage.type_journee == "normal"
        assert pointage.site_id == self.site.id
        # Un Scan a bien été créé par process_scan (pas de deuxième moteur
        # d'écriture indépendant côté serializer).
        assert Scan.objects.filter(employe=self.employe, type_scan="entree_matin").exists()

    def test_sequence_e1_s1_e2_s2_via_api_pointages(self):
        jour = date(2026, 8, 10)
        creneaux = [(8, 0), (12, 0), (13, 0), (17, 0)]
        codes_attendus = ["entree_matin", "sortie_matin", "entree_apres_midi", "sortie_apres_midi"]

        for (hh, mm), code_attendu in zip(creneaux, codes_attendus):
            now = _aware(jour, hh, mm)
            with patch("pointage.services.timezone.now", return_value=now):
                response = self._post_pointages_api()
            assert response.status_code == 201, (code_attendu, response.content)

        matin = Pointage.objects.get(employe=self.employe, periode="matin")
        apres_midi = Pointage.objects.get(employe=self.employe, periode="apres_midi")
        assert matin.heure_arrivee == dtime(8, 0)
        assert matin.heure_depart == dtime(12, 0)
        assert apres_midi.heure_arrivee == dtime(13, 0)
        assert apres_midi.heure_depart == dtime(17, 0)

    def test_meme_resultat_via_api_pointages_et_via_mobile(self):
        """Même scénario (première entrée du matin), deux points d'entrée
        différents (deux employés distincts pour éviter l'anti-doublon
        entre les deux appels) -> même décision, même Pointage produit."""
        employe_mobile = Employe.objects.create(
            nom="Test", prenom="Mobile", matricule="APIT02",
            qr_code_token="33333333-3333-3333-3333-333333333333", actif=True,
        )
        now = _aware(date(2026, 8, 10), 8, 0)

        with patch("pointage.services.timezone.now", return_value=now):
            resp_api = self._post_pointages_api()
        with patch("pointage.services.timezone.now", return_value=now):
            resp_mobile = self._post_mobile_scan(employe=employe_mobile)

        assert resp_api.status_code == 201
        assert resp_mobile.status_code == 201

        p_api = Pointage.objects.get(employe=self.employe)
        p_mobile = Pointage.objects.get(employe=employe_mobile)
        assert p_api.periode == p_mobile.periode == "matin"
        assert p_api.heure_arrivee == p_mobile.heure_arrivee == dtime(8, 0)
        assert p_api.type_journee == p_mobile.type_journee == "normal"


class TestParisGardeEtMinuit(PointageSerializerProcessScanTestCase):
    def test_garde_via_api_pointages(self):
        Pointage.objects.create(employe=self.employe, site=self.site, date_pointage=date(2026, 8, 10), periode="nuit", type_journee="garde", statut="absent")
        now = _aware(date(2026, 8, 10), 20, 0)
        with patch("pointage.services.timezone.now", return_value=now):
            response = self._post_pointages_api(extra={"periode": "nuit", "type_journee": "garde"})

        assert response.status_code == 201, response.content
        pointage = Pointage.objects.get(employe=self.employe, periode="nuit")
        assert pointage.type_journee == "garde"
        assert pointage.heure_arrivee == dtime(20, 0)

    def test_garde_apres_minuit_via_api_pointages(self):
        jour1, jour2 = date(2026, 8, 10), date(2026, 8, 11)
        Pointage.objects.create(employe=self.employe, site=self.site, date_pointage=jour1, periode="nuit", type_journee="garde", statut="absent")

        with patch("pointage.services.timezone.now", return_value=_aware(jour1, 22, 0)):
            resp_debut = self._post_pointages_api(extra={"periode": "nuit", "type_journee": "garde"})
        assert resp_debut.status_code == 201, resp_debut.content

        with patch("pointage.services.timezone.now", return_value=_aware(jour2, 6, 0)):
            resp_fin = self._post_pointages_api(extra={"periode": "nuit", "type_journee": "garde"})
        assert resp_fin.status_code == 201, resp_fin.content

        pointage = Pointage.objects.get(employe=self.employe, periode="nuit")
        assert pointage.date_pointage == jour1
        assert pointage.heure_arrivee == dtime(22, 0)
        assert pointage.heure_depart == dtime(6, 0)
        assert pointage.date_depart == jour2

    def test_force_new_via_api_pointages_ignore_garde_oubliee(self):
        avant_hier = date(2026, 8, 8)
        Pointage.objects.create(employe=self.employe, site=self.site, date_pointage=avant_hier, periode="nuit", type_journee="garde", statut="absent")
        with patch("pointage.services.timezone.now", return_value=_aware(avant_hier, 20, 0)):
            self._post_pointages_api(extra={"periode": "nuit", "type_journee": "garde"})

        aujourdhui = date(2026, 8, 10)
        with patch("pointage.services.timezone.now", return_value=_aware(aujourdhui, 20, 0)):
            response = self._post_pointages_api(
                extra={"periode": "nuit", "type_journee": "garde", "force_new": True}
            )

        assert response.status_code == 201, response.content
        assert Pointage.objects.filter(
            employe=self.employe, periode="nuit", date_pointage=aujourdhui
        ).exists()


class TestProtectionsPreserveesViaApiPointages(PointageSerializerProcessScanTestCase):
    """Les protections de process_scan() (anti-doublon, employé
    inactif) doivent s'appliquer identiquement en passant par le
    serializer REST — il n'y a plus de deuxième chemin qui les
    contournerait."""

    def test_double_scan_via_api_pointages_est_refuse(self):
        now = _aware(date(2026, 8, 10), 8, 0)
        with patch("pointage.services.timezone.now", return_value=now):
            premier = self._post_pointages_api()
            second = self._post_pointages_api()

        assert premier.status_code == 201
        assert second.status_code == 400
        assert second.json()["code"] == "DOUBLON"
        # Un seul Pointage/Scan malgré les deux appels.
        assert Pointage.objects.filter(employe=self.employe).count() == 1
        assert Scan.objects.filter(employe=self.employe).count() == 1

    def test_employe_inactif_via_api_pointages_est_refuse(self):
        self.employe.actif = False
        self.employe.save()

        now = _aware(date(2026, 8, 10), 8, 0)
        with patch("pointage.services.timezone.now", return_value=now):
            response = self._post_pointages_api()

        assert response.status_code == 400
        assert response.json()["code"] == "QR_INVALIDE"
        assert not Pointage.objects.filter(employe=self.employe).exists()

    def test_site_invalide_via_api_pointages_est_refuse(self):
        now = _aware(date(2026, 8, 10), 8, 0)
        with patch("pointage.services.timezone.now", return_value=now):
            response = self.admin_client.post(
                "/api/pointages/", {"employe": self.employe.id, "site": 999999}
            )

        # 'site' est un PrimaryKeyRelatedField : un ID inexistant est déjà
        # rejeté au niveau validation du serializer (avant même d'atteindre
        # create()/process_scan()) -> 400 dans tous les cas.
        assert response.status_code == 400
        assert not Pointage.objects.filter(employe=self.employe).exists()

    def test_utilisateur_non_admin_ne_peut_pas_creer_via_api_pointages(self):
        """Garde-fou existant (test_pointage_permissions.py) : ce chemin
        reste réservé à l'admin/RH même après le passage par
        process_scan()."""
        client = Client()
        client.force_login(self.operateur)
        response = client.post(
            "/api/pointages/", {"employe": self.employe.id, "site": self.site.id}
        )
        assert response.status_code == 403
        assert not Pointage.objects.filter(employe=self.employe).exists()
