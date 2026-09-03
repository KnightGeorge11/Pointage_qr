from datetime import time as dtime, date

from django.test import TestCase, Client
from django.urls import reverse

from pointage.models import (
    AnomaliePointage, AnomalieTraitement, CustomUser, Employe, Site, Pointage,
)
from pointage.anomalies import enregistrer_anomalie


class AlerteDetailTestCase(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username="admin_detail", password="pass1234", role="admin", is_staff=True,
        )
        self.utilisateur = CustomUser.objects.create_user(
            username="user_detail", password="pass1234", role="user",
        )
        self.employe = Employe.objects.create(
            nom="Dupont", prenom="Jean", matricule="E030", actif=True
        )
        self.site = Site.objects.create(
            nom="Site", adresse="a",
            heure_ouverture_matin=dtime(8, 0), heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 30), heure_fermeture_apres_midi=dtime(17, 30),
        )

    def _url(self, anomalie):
        return reverse('alerte_detail', args=[anomalie.pk])


class TestPermissionsPageDetail(AlerteDetailTestCase):
    def setUp(self):
        super().setUp()
        self.anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK, message="x",
            employe=self.employe, date_pointage=date.today(),
        )

    def test_utilisateur_normal_ne_peut_pas_consulter(self):
        client = Client()
        client.force_login(self.utilisateur)
        response = client.get(self._url(self.anomalie))
        assert response.status_code == 403

    def test_utilisateur_normal_ne_peut_pas_traiter_via_post_direct(self):
        client = Client()
        client.force_login(self.utilisateur)
        response = client.post(self._url(self.anomalie), {
            'type_action': 'justification', 'commentaire': 'tentative non autorisée',
        })
        assert response.status_code == 403
        self.anomalie.refresh_from_db()
        assert self.anomalie.statut == AnomaliePointage.STATUT_OUVERTE

    def test_anonyme_ne_peut_pas_consulter(self):
        client = Client()
        response = client.get(self._url(self.anomalie))
        assert response.status_code == 302

    def test_admin_peut_consulter(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(self._url(self.anomalie))
        assert response.status_code == 200
        assert "Anomalie #" in response.content.decode()

    def test_alertes_rh_view_liste_non_accessible_a_un_utilisateur_normal(self):
        client = Client()
        client.force_login(self.utilisateur)
        response = client.get(reverse('alertes_rh'))
        assert response.status_code == 403


class TestActionCorriger(AlerteDetailTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.admin)

    def test_corriger_sans_commentaire_est_refuse_et_ne_touche_pas_le_pointage(self):
        pointage = Pointage.objects.create(
            employe=self.employe, site=self.site, date_pointage=date.today(),
            periode='matin', type_journee='normal', heure_arrivee=dtime(8, 5),
        )
        anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_MISSING_MORNING_EXIT, message="x",
            employe=self.employe, site=self.site, date_pointage=date.today(),
        )
        self.client.post(self._url(anomalie), {
            'type_action': 'correction', 'commentaire': '',
            'employe': self.employe.id, 'site': self.site.id,
            'date_pointage': date.today().isoformat(), 'periode': 'matin',
            'type_journee': 'normal', 'heure_arrivee': '08:05', 'heure_depart': '12:03',
            'statut': 'present', 'notes': '',
        })
        pointage.refresh_from_db()
        assert pointage.heure_depart is None
        anomalie.refresh_from_db()
        assert anomalie.statut == AnomaliePointage.STATUT_OUVERTE
        assert AnomalieTraitement.objects.filter(anomalie=anomalie).count() == 0

    def test_corriger_avec_commentaire_modifie_le_pointage_et_trace_le_diff(self):
        pointage = Pointage.objects.create(
            employe=self.employe, site=self.site, date_pointage=date.today(),
            periode='matin', type_journee='normal', heure_arrivee=dtime(8, 5),
        )
        anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_MISSING_MORNING_EXIT, message="Sortie matin manquante",
            employe=self.employe, site=self.site, date_pointage=date.today(),
        )
        response = self.client.post(self._url(anomalie), {
            'type_action': 'correction',
            'commentaire': "L'employé a oublié de scanner sa sortie du matin.",
            'employe': self.employe.id, 'site': self.site.id,
            'date_pointage': date.today().isoformat(), 'periode': 'matin',
            'type_journee': 'normal', 'heure_arrivee': '08:05', 'heure_depart': '12:03',
            'statut': 'present', 'notes': '',
        }, follow=True)
        assert response.status_code == 200
        pointage.refresh_from_db()
        assert pointage.heure_depart == dtime(12, 3)
        anomalie.refresh_from_db()
        assert anomalie.statut == AnomaliePointage.STATUT_TRAITEE
        assert anomalie.traitement.type_action == AnomalieTraitement.ACTION_CORRECTION
        assert anomalie.traitement.pointage_concerne == pointage
        diff = next(c for c in anomalie.traitement.corrections if c['champ'] == 'heure_depart')
        assert diff['ancienne_valeur'] in (None, 'None')
        assert '12:03' in diff['nouvelle_valeur']


class TestActionJustifier(AlerteDetailTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.admin)
        self.anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_OUTSIDE_HOURS, message="Scan en dehors des horaires",
            employe=self.employe, date_pointage=date.today(),
        )

    def test_justifier_sans_commentaire_est_refuse(self):
        self.client.post(self._url(self.anomalie), {
            'type_action': 'justification', 'commentaire': '',
        })
        self.anomalie.refresh_from_db()
        assert self.anomalie.statut == AnomaliePointage.STATUT_OUVERTE

    def test_justifier_ne_touche_jamais_le_pointage(self):
        assert Pointage.objects.count() == 0
        response = self.client.post(self._url(self.anomalie), {
            'type_action': 'justification',
            'commentaire': 'Intervention exceptionnelle autorisée par le responsable.',
        }, follow=True)
        assert response.status_code == 200
        assert Pointage.objects.count() == 0
        self.anomalie.refresh_from_db()
        assert self.anomalie.statut == AnomaliePointage.STATUT_TRAITEE
        assert self.anomalie.traitement.type_action == AnomalieTraitement.ACTION_JUSTIFICATION
        assert self.anomalie.traitement.corrections == []


class TestActionRejeter(AlerteDetailTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.admin)
        self.anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_INVALID_QR, message="Scan invalide",
            matricule_scanne="E999", date_pointage=date.today(),
        )

    def test_rejeter_necessite_un_commentaire(self):
        self.client.post(self._url(self.anomalie), {
            'type_action': 'rejet', 'commentaire': ''
        })
        self.anomalie.refresh_from_db()
        assert self.anomalie.statut == AnomaliePointage.STATUT_OUVERTE

    def test_rejeter_marque_traitee_sans_modification(self):
        response = self.client.post(self._url(self.anomalie), {
            'type_action': 'rejet',
            'commentaire': 'Scan accidentel, aucune présence réelle.',
        }, follow=True)
        assert response.status_code == 200
        self.anomalie.refresh_from_db()
        assert self.anomalie.statut == AnomaliePointage.STATUT_TRAITEE
        assert self.anomalie.traitement.type_action == AnomalieTraitement.ACTION_REJET


class TestCloture(AlerteDetailTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.admin)

    def test_cloturer_une_anomalie_traitee(self):
        anomalie = enregistrer_anomalie(AnomaliePointage.TYPE_DURING_BREAK, message="x")
        self.client.post(self._url(anomalie), {
            'type_action': 'justification', 'commentaire': 'ok'
        })
        anomalie.refresh_from_db()
        assert anomalie.statut == AnomaliePointage.STATUT_TRAITEE
        self.client.post(self._url(anomalie), {'type_action': 'cloturer'})
        anomalie.refresh_from_db()
        assert anomalie.statut == AnomaliePointage.STATUT_CLOTUREE
        assert anomalie.cloturee_par == self.admin

    def test_anomalie_cloturee_ne_peut_plus_etre_modifiee(self):
        anomalie = enregistrer_anomalie(AnomaliePointage.TYPE_DURING_BREAK, message="x")
        self.client.post(self._url(anomalie), {
            'type_action': 'justification', 'commentaire': 'ok'
        })
        anomalie.refresh_from_db()
        self.client.post(self._url(anomalie), {'type_action': 'cloturer'})
        anomalie.refresh_from_db()
        assert anomalie.statut == AnomaliePointage.STATUT_CLOTUREE
        response = self.client.post(self._url(anomalie), {
            'type_action': 'rejet', 'commentaire': 'nouvelle tentative',
        }, follow=True)
        anomalie.refresh_from_db()
        assert response.status_code == 200
        assert anomalie.statut == AnomaliePointage.STATUT_CLOTUREE
        assert anomalie.traitement.type_action == AnomalieTraitement.ACTION_JUSTIFICATION

    def test_utilisateur_ne_peut_pas_cloturer(self):
        anomalie = enregistrer_anomalie(AnomaliePointage.TYPE_DURING_BREAK, message="x")
        self.client.post(self._url(anomalie), {
            'type_action': 'justification', 'commentaire': 'ok'
        })
        anomalie.refresh_from_db()
        client_user = Client()
        client_user.force_login(self.utilisateur)
        response = client_user.post(self._url(anomalie), {'type_action': 'cloturer'})
        anomalie.refresh_from_db()
        assert response.status_code == 403
        assert anomalie.statut == AnomaliePointage.STATUT_TRAITEE
