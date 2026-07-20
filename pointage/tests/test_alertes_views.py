# pointage/tests/test_alertes_views.py
#
# Tests de la vue web des anomalies (Phase 4) : rendu des templates,
# filtres, actions traiter/clôturer via le client Django. Sert aussi de
# garde-fou contre les erreurs de template (alertes_rh.html, badge du
# dashboard) qu'un test purement unitaire ne détecterait pas.

from datetime import date

from django.test import TestCase, Client
from django.urls import reverse

from pointage.models import AnomaliePointage, CustomUser
from pointage.anomalies import enregistrer_anomalie, marquer_traitee


class TestAlertesRHView(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username="admin_test", password="pass1234", role="admin", is_staff=True,
        )
        self.client = Client()
        self.client.force_login(self.admin)

    def test_page_anomalies_accessible_et_rend_le_template(self):
        enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK, message="Scan pendant la pause",
            date_pointage=date.today(),
        )
        response = self.client.get(reverse('alertes_rh'))

        assert response.status_code == 200
        assert "Anomalies de pointage" in response.content.decode()

    def test_page_anomalies_refuse_utilisateur_non_connecte(self):
        client_anonyme = Client()
        response = client_anonyme.get(reverse('alertes_rh'))
        assert response.status_code in (302, 403)

    def test_liste_vide_affiche_message_approprie(self):
        response = self.client.get(reverse('alertes_rh'))
        assert response.status_code == 200
        assert "Aucune anomalie" in response.content.decode()

    def test_filtre_par_type(self):
        enregistrer_anomalie(AnomaliePointage.TYPE_DURING_BREAK, message="A")
        enregistrer_anomalie(AnomaliePointage.TYPE_DAY_COMPLETE, message="B")

        response = self.client.get(reverse('alertes_rh'), {'type': AnomaliePointage.TYPE_DAY_COMPLETE})
        content = response.content.decode()
        assert "Journée déjà terminée" in content

    def test_filtre_par_statut(self):
        ouverte = enregistrer_anomalie(AnomaliePointage.TYPE_DURING_BREAK, message="Ouverte")
        traitee = enregistrer_anomalie(AnomaliePointage.TYPE_DAY_COMPLETE, message="Traitee")
        marquer_traitee(traitee, self.admin, commentaire="ok")

        response = self.client.get(reverse('alertes_rh'), {'statut': 'ouverte'})
        content = response.content.decode()
        assert "Ouverte" in content
        assert "Traitee" not in content

    def test_traiter_une_anomalie_via_le_formulaire(self):
        anomalie = enregistrer_anomalie(AnomaliePointage.TYPE_DURING_BREAK, message="x")

        response = self.client.post(reverse('alertes_rh'), {
            'anomalie_id': anomalie.pk,
            'action': 'traiter',
            'commentaire': 'Vérifié, faux positif.',
        }, follow=True)

        anomalie.refresh_from_db()
        assert response.status_code == 200
        assert anomalie.statut == AnomaliePointage.STATUT_TRAITEE
        assert anomalie.traitement.commentaire == 'Vérifié, faux positif.'
        assert anomalie.traitement.administrateur == self.admin

    def test_traiter_avec_correction_de_pointage(self):
        anomalie = enregistrer_anomalie(AnomaliePointage.TYPE_MISSING_MORNING_EXIT, message="x")

        self.client.post(reverse('alertes_rh'), {
            'anomalie_id': anomalie.pk,
            'action': 'traiter',
            'commentaire': 'Sortie oubliée, corrigée manuellement.',
            'champ_corrige': 'heure_depart',
            'ancienne_valeur': '',
            'nouvelle_valeur': '12:00',
        }, follow=True)

        anomalie.refresh_from_db()
        assert anomalie.traitement.corrections == [{
            'champ': 'heure_depart', 'ancienne_valeur': '', 'nouvelle_valeur': '12:00',
        }]

    def test_cloturer_une_anomalie_traitee(self):
        anomalie = enregistrer_anomalie(AnomaliePointage.TYPE_DURING_BREAK, message="x")
        marquer_traitee(anomalie, self.admin, commentaire="ok")

        response = self.client.post(reverse('alertes_rh'), {
            'anomalie_id': anomalie.pk,
            'action': 'cloturer',
        }, follow=True)

        anomalie.refresh_from_db()
        assert response.status_code == 200
        assert anomalie.statut == AnomaliePointage.STATUT_CLOTUREE
        assert anomalie.cloturee_par == self.admin

    def test_cloturer_une_anomalie_ouverte_est_refuse_avec_message(self):
        anomalie = enregistrer_anomalie(AnomaliePointage.TYPE_DURING_BREAK, message="x")

        response = self.client.post(reverse('alertes_rh'), {
            'anomalie_id': anomalie.pk,
            'action': 'cloturer',
        }, follow=True)

        anomalie.refresh_from_db()
        assert anomalie.statut == AnomaliePointage.STATUT_OUVERTE
        messages = list(response.context['messages'])
        assert any('❌' in str(m) for m in messages)


class TestDashboardBadge(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username="admin_dash", password="pass1234", role="admin", is_staff=True,
        )
        self.client = Client()
        self.client.force_login(self.admin)

    def test_dashboard_sans_anomalie_nafiche_pas_le_badge(self):
        response = self.client.get(reverse('dashboard'))
        assert response.status_code == 200
        assert 'class="anomalies-badge"' not in response.content.decode()

    def test_dashboard_avec_anomalie_ouverte_affiche_le_badge(self):
        enregistrer_anomalie(AnomaliePointage.TYPE_DURING_BREAK, message="x")

        response = self.client.get(reverse('dashboard'))
        content = response.content.decode()
        assert response.status_code == 200
        assert 'anomalies-badge' in content
        assert '1 anomalie ouverte' in content
