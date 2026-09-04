from datetime import date

from django.test import Client, TestCase
from django.urls import reverse

from pointage.anomalies import enregistrer_anomalie
from pointage.models import AnomaliePointage, AnomalieTraitement, CustomUser, Employe


class AdminAnomalyWorkflowTests(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username="rh_workflow",
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
            message="Anomalie workflow",
            employe=self.employe,
            date_pointage=date.today(),
        )
        self.client = Client()

    def url(self):
        return reverse("admin_anomaly_workflow", args=[self.anomalie.pk])

    def test_get_workflow_est_accessible_dans_espace_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url())

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Traitement de l’anomalie", content)
        self.assertIn("Justifier", content)
        self.assertIn("Rejeter", content)
        self.assertIn("Corriger le pointage", content)

    def test_utilisateur_normal_ne_peut_pas_acceder_au_workflow(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url())

        self.assertEqual(response.status_code, 403)

    def test_justification_sans_commentaire_est_refusee(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url(), {"action": "justification"})

        self.assertEqual(response.status_code, 302)
        self.anomalie.refresh_from_db()
        self.assertEqual(self.anomalie.statut, AnomaliePointage.STATUT_OUVERTE)
        self.assertFalse(
            AnomalieTraitement.objects.filter(anomalie=self.anomalie).exists()
        )

    def test_justification_fait_ouverte_vers_traitee(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            self.url(),
            {
                "action": "justification",
                "commentaire": "Justification RH vérifiée et documentée.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.anomalie.refresh_from_db()
        self.assertEqual(self.anomalie.statut, AnomaliePointage.STATUT_TRAITEE)
        traitement = self.anomalie.traitement
        self.assertEqual(traitement.type_action, AnomalieTraitement.ACTION_JUSTIFICATION)
        self.assertEqual(traitement.administrateur, self.admin)

    def test_cloture_directe_dune_anomalie_ouverte_est_refusee(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url(), {"action": "cloture"})

        self.assertEqual(response.status_code, 302)
        self.anomalie.refresh_from_db()
        self.assertEqual(self.anomalie.statut, AnomaliePointage.STATUT_OUVERTE)

    def test_traitee_vers_cloturee_puis_verrouillee(self):
        self.client.force_login(self.admin)
        self.client.post(
            self.url(),
            {
                "action": "justification",
                "commentaire": "Anomalie vérifiée avant clôture.",
            },
        )

        self.anomalie.refresh_from_db()
        self.assertEqual(self.anomalie.statut, AnomaliePointage.STATUT_TRAITEE)

        response = self.client.post(self.url(), {"action": "cloture"})
        self.assertEqual(response.status_code, 302)

        self.anomalie.refresh_from_db()
        self.assertEqual(self.anomalie.statut, AnomaliePointage.STATUT_CLOTUREE)

        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("Dossier clôturé", response.content.decode())

        response = self.client.post(
            self.url(),
            {"action": "justification", "commentaire": "Tentative après clôture."},
        )
        self.assertEqual(response.status_code, 302)
        self.anomalie.refresh_from_db()
        self.assertEqual(self.anomalie.statut, AnomaliePointage.STATUT_CLOTUREE)

    def test_action_corriger_reste_dans_admin(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url(), {"action": "corriger"})

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/", response["Location"])
        self.assertIn("corriger-pointage", response["Location"])
