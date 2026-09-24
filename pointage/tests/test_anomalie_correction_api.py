from datetime import date, time

from django.test import TestCase

from rest_framework.test import APIClient

from pointage.models import (
    AnomaliePointage,
    CustomUser,
    Employe,
    Pointage,
    PointageAudit,
    Site,
)
from pointage.anomalies import enregistrer_anomalie


class TestAnomalieCorrectionAPI(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username="api_admin",
            password="pass1234",
            role="admin",
            is_staff=True,
            is_superuser=True,
        )
        self.user = CustomUser.objects.create_user(
            username="api_user",
            password="pass1234",
            role="user",
        )
        self.employe = Employe.objects.create(
            nom="API",
            prenom="Test",
            matricule="API001",
            actif=True,
        )
        self.site = Site.objects.create(
            nom="Site API",
            adresse="1 rue API",
            heure_ouverture_matin=time(8, 0),
            heure_fermeture_matin=time(12, 0),
            heure_ouverture_apres_midi=time(13, 0),
            heure_fermeture_apres_midi=time(17, 0),
        )
        self.client = APIClient()

    def _url(self, anomalie):
        return f"/api/anomalies/{anomalie.pk}/traiter/"

    def test_correction_api_modifie_reellement_le_pointage_et_audite(self):
        pointage = Pointage.objects.create(
            employe=self.employe,
            site=self.site,
            date_pointage=date.today(),
            periode="matin",
            type_journee="normal",
            heure_arrivee=time(8, 0),
        )
        anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_MISSING_MORNING_EXIT,
            message="Sortie matin manquante",
            employe=self.employe,
            site=self.site,
            date_pointage=date.today(),
            contexte={"periode": "matin"},
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            self._url(anomalie),
            {
                "commentaire": "Sortie vérifiée par RH.",
                "corrections": [
                    {
                        "champ": "heure_depart",
                        "ancienne_valeur": None,
                        "nouvelle_valeur": "12:05",
                    }
                ],
            },
            format="json",
        )

        assert response.status_code == 200
        pointage.refresh_from_db()
        anomalie.refresh_from_db()

        assert pointage.heure_depart == time(12, 5)
        assert anomalie.statut == AnomaliePointage.STATUT_TRAITEE
        assert anomalie.traitement.pointage_concerne_id == pointage.id
        assert anomalie.traitement.corrections == [{
            "champ": "heure_depart",
            "ancienne_valeur": None,
            "nouvelle_valeur": "12:05:00",
        }]

        audit = PointageAudit.objects.get(pointage=pointage)
        assert audit.action == PointageAudit.ACTION_UPDATE
        assert audit.administrateur == self.admin
        assert audit.avant["heure_depart"] is None
        assert audit.apres["heure_depart"] == "12:05:00"

    def test_correction_api_peut_creer_un_pointage(self):
        anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK,
            message="Scan pendant la pause",
            employe=self.employe,
            site=self.site,
            date_pointage=date.today(),
            contexte={"periode": "matin"},
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            self._url(anomalie),
            {
                "commentaire": "Travail confirmé.",
                "pointage": {
                    "site": self.site.id,
                    "date_pointage": date.today().isoformat(),
                    "periode": "matin",
                    "type_journee": "normal",
                    "heure_arrivee": "08:00",
                    "heure_depart": "12:00",
                    "statut": "present",
                    "notes": "Correction RH",
                },
            },
            format="json",
        )

        assert response.status_code == 200
        pointage = Pointage.objects.get(employe=self.employe, periode="matin")
        assert pointage.heure_arrivee == time(8, 0)
        assert pointage.heure_depart == time(12, 0)

        audit = PointageAudit.objects.get(pointage=pointage)
        assert audit.action == PointageAudit.ACTION_CREATE

    def test_api_peut_justifier_sans_modifier_le_pointage(self):
        anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK,
            message="Faux positif",
            employe=self.employe,
            site=self.site,
            date_pointage=date.today(),
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            self._url(anomalie),
            {"commentaire": "Faux positif confirmé."},
            format="json",
        )

        assert response.status_code == 200
        anomalie.refresh_from_db()
        assert anomalie.statut == AnomaliePointage.STATUT_TRAITEE
        assert anomalie.traitement.type_action == "justification"
        assert PointageAudit.objects.count() == 0

    def test_api_refuse_un_utilisateur_non_rh(self):
        anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK,
            message="x",
            employe=self.employe,
            site=self.site,
            date_pointage=date.today(),
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self._url(anomalie),
            {
                "corrections": [
                    {"champ": "heure_depart", "nouvelle_valeur": "12:00"}
                ]
            },
            format="json",
        )

        assert response.status_code == 403
        assert Pointage.objects.count() == 0
        anomalie.refresh_from_db()
        assert anomalie.statut == AnomaliePointage.STATUT_OUVERTE
