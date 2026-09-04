from datetime import date

from django.test import Client, TestCase
from django.urls import reverse

from pointage.anomalies import enregistrer_anomalie
from pointage.models import AnomaliePointage, AnomalieTraitement, CustomUser, Employe


class TestWorkflowAnomalieJazzmin(TestCase):
    """Vérifie le workflow RH exposé dans l'espace d'administration."""

    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username="admin_workflow",
            password="pass1234",
            role="admin",
            is_staff=True,
            is_superuser=True,
        )
        self.user = CustomUser.objects.create_user(
            username="user_workflow",
            password="pass1234",
            role="user",
        )
        self.employe = Employe.objects.create(
            nom="Workflow",
            prenom="Test",
            matricule="WF001",
            actif=True,
        )
        self.anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK,
            message="Scan pendant la pause",
            employe=self.employe,
            date_pointage=date.today(),
        )
        self.client = Client()
        self.url = reverse("admin_anomaly_workflow", args=[self.anomalie.pk])

    def test_admin_peut_ouvrir_le_workflow_dans_l_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        assert response.status_code == 200
        body = response.content.decode()
        assert "Traitement de l'anomalie" in body
        assert "Justifier" in body
        assert "Rejeter" in body
        assert "Corriger le pointage" in body

    def test_utilisateur_normal_est_refuse(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        assert response.status_code == 403

    def test_justification_exige_un_commentaire_et_traite_l_anomalie(self):
        self.client.force_login(self.admin)

        response = self.client.post(self.url, {
            "action": "justification",
            "commentaire": "Justification vérifiée par le RH.",
        })

        assert response.status_code == 302
        self.anomalie.refresh_from_db()
        assert self.anomalie.statut == AnomaliePointage.STATUT_TRAITEE
        traitement = AnomalieTraitement.objects.get(anomalie=self.anomalie)
        assert traitement.type_action == AnomalieTraitement.ACTION_JUSTIFICATION
        assert traitement.administrateur == self.admin
        assert traitement.commentaire == "Justification vérifiée par le RH."

    def test_justification_sans_commentaire_ne_traite_pas(self):
        self.client.force_login(self.admin)

        self.client.post(self.url, {
            "action": "justification",
            "commentaire": "",
        })

        self.anomalie.refresh_from_db()
        assert self.anomalie.statut == AnomaliePointage.STATUT_OUVERTE
        assert not AnomalieTraitement.objects.filter(anomalie=self.anomalie).exists()

    def test_rejet_exige_un_motif(self):
        self.client.force_login(self.admin)

        self.client.post(self.url, {
            "action": "rejet",
            "commentaire": "Motif de rejet vérifié.",
        })

        self.anomalie.refresh_from_db()
        assert self.anomalie.statut == AnomaliePointage.STATUT_TRAITEE
        traitement = AnomalieTraitement.objects.get(anomalie=self.anomalie)
        assert traitement.type_action == AnomalieTraitement.ACTION_REJET

    def test_une_anomalie_ouverte_ne_peut_pas_etre_cloturee_directement(self):
        self.client.force_login(self.admin)

        self.client.post(self.url, {"action": "cloture"})

        self.anomalie.refresh_from_db()
        assert self.anomalie.statut == AnomaliePointage.STATUT_OUVERTE

    def test_une_anomalie_traitee_peut_etre_cloturee(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, {
            "action": "justification",
            "commentaire": "Traitement préalable effectué.",
        })

        self.anomalie.refresh_from_db()
        assert self.anomalie.statut == AnomaliePointage.STATUT_TRAITEE

        self.client.post(self.url, {"action": "cloture"})

        self.anomalie.refresh_from_db()
        assert self.anomalie.statut == AnomaliePointage.STATUT_CLOTUREE
        assert self.anomalie.cloturee_par == self.admin
        assert self.anomalie.date_cloture is not None

    def test_anomalie_cloturee_est_verrouillee(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, {
            "action": "justification",
            "commentaire": "Traitement préalable effectué.",
        })
        self.client.post(self.url, {"action": "cloture"})

        self.client.post(self.url, {
            "action": "justification",
            "commentaire": "Tentative de modification après clôture.",
        })

        self.anomalie.refresh_from_db()
        assert self.anomalie.statut == AnomaliePointage.STATUT_CLOTUREE
        assert AnomalieTraitement.objects.filter(anomalie=self.anomalie).count() == 1
