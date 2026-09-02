# pointage/tests/test_anomalie_correction_admin.py
#
# Vérifie le flux : Anomalie -> Admin/RH -> correction réelle du
# Pointage -> traçabilité (AnomalieTraitement) -> anomalie traitée.
#
# Réutilise PointageForm (déjà existant) et marquer_traitee() (déjà
# existant, Phase 4) — cette vue ne fait qu'exposer les deux ensemble
# dans l'admin. Aucune nouvelle logique de pointage n'est testée ici,
# seulement le branchement.

from datetime import time as dtime, date

from django.test import TestCase, Client
from django.urls import reverse

from pointage.models import (
    AnomaliePointage, AnomalieTraitement, CustomUser, Employe, Site, Pointage,
)
from pointage.anomalies import enregistrer_anomalie


class TestPermissionsCorrectionAnomalie(TestCase):
    """Seul un utilisateur is_staff (role='admin') peut accéder à la
    correction. Un compte 'utilisateur' (scanner) ne doit jamais pouvoir
    créer ou modifier un pointage par ce biais."""

    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username="admin_correction", password="pass1234",
            role="admin", is_staff=True, is_superuser=True,
        )
        self.utilisateur = CustomUser.objects.create_user(
            username="user_correction", password="pass1234",
            role="user",
        )
        self.employe = Employe.objects.create(nom="Rakoto", prenom="Jean", matricule="E001", actif=True)
        self.anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK, message="x",
            employe=self.employe, date_pointage=date.today(),
        )

    def _url(self):
        return reverse('admin:anomalie_corriger_pointage', args=[self.anomalie.pk])

    def test_utilisateur_non_staff_est_bloque(self):
        """Un compte 'utilisateur' (le rôle du scanner) créé avec
        role='user' n'a pas is_staff -> Django admin doit refuser
        l'accès (redirection vers le login, jamais un 200 avec le
        formulaire de correction)."""
        assert self.utilisateur.is_staff is False  # confirme le postulat du rôle

        client = Client()
        client.force_login(self.utilisateur)
        response = client.get(self._url())

        assert response.status_code in (302, 403)
        # Aucun pointage ne doit avoir pu être créé/modifié via un GET refusé
        assert Pointage.objects.count() == 0

    def test_anonyme_est_bloque(self):
        client = Client()
        response = client.get(self._url())
        assert response.status_code in (302, 403)

    def test_admin_staff_peut_acceder_au_formulaire(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(self._url())

        assert response.status_code == 200
        assert "Corriger le pointage" in response.content.decode()

    def test_utilisateur_ne_peut_pas_soumettre_de_correction(self):
        """Même en tentant un POST direct, un compte non-staff ne doit
        jamais pouvoir créer un Pointage par ce biais."""
        client = Client()
        client.force_login(self.utilisateur)
        response = client.post(self._url(), {
            'employe': self.employe.id, 'date_pointage': date.today().isoformat(),
            'periode': 'matin', 'type_journee': 'normal',
            'heure_arrivee': '08:00', 'commentaire': 'tentative non autorisée',
        })

        assert response.status_code in (302, 403)
        assert Pointage.objects.count() == 0
        self.anomalie.refresh_from_db()
        assert self.anomalie.statut == AnomaliePointage.STATUT_OUVERTE


class TestCorrectionReelleDuPointage(TestCase):
    """La correction doit réellement créer/modifier le Pointage en base,
    pas seulement changer le statut de l'anomalie."""

    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username="admin_correction2", password="pass1234",
            role="admin", is_staff=True, is_superuser=True,
        )
        self.employe = Employe.objects.create(nom="Rasoa", prenom="Marie", matricule="E002", actif=True)
        self.site = Site.objects.create(
            nom="Site A", adresse="1 rue A",
            heure_ouverture_matin=dtime(8, 0), heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 30), heure_fermeture_apres_midi=dtime(17, 30),
        )
        self.client = Client()
        self.client.force_login(self.admin)

    def _url(self, anomalie):
        return reverse('admin:anomalie_corriger_pointage', args=[anomalie.pk])

    def test_creer_un_nouveau_pointage_depuis_une_anomalie_sans_pointage_existant(self):
        """Cas 'scan pendant la pause' : aucun Pointage n'existe encore.
        L'admin doit pouvoir en créer un directement depuis l'anomalie."""
        anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK, message="Scan pendant la pause",
            employe=self.employe, site=self.site, date_pointage=date.today(),
        )
        assert Pointage.objects.count() == 0

        response = self.client.post(self._url(anomalie), {
            'employe': self.employe.id, 'site': self.site.id,
            'date_pointage': date.today().isoformat(), 'periode': 'matin',
            'type_journee': 'normal', 'heure_arrivee': '08:00', 'heure_depart': '12:00',
            'statut': 'present', 'notes': '',
            'commentaire': "L'employé a bien travaillé le matin, oubli de badge corrigé.",
        }, follow=True)

        assert response.status_code == 200
        pointage = Pointage.objects.get(employe=self.employe, periode='matin')
        assert pointage.heure_arrivee == dtime(8, 0)
        assert pointage.heure_depart == dtime(12, 0)

        anomalie.refresh_from_db()
        assert anomalie.statut == AnomaliePointage.STATUT_TRAITEE
        assert anomalie.traitement.pointage_concerne == pointage
        assert anomalie.traitement.administrateur == self.admin
        assert "oubli de badge" in anomalie.traitement.commentaire

    def test_corriger_un_pointage_existant_sortie_matin_oubliee(self):
        """Cas 'sortie matin manquante' : le Pointage matin existe déjà
        (heure_arrivee posée), il faut pouvoir y ajouter heure_depart."""
        pointage_matin = Pointage.objects.create(
            employe=self.employe, site=self.site, date_pointage=date.today(),
            periode='matin', type_journee='normal', heure_arrivee=dtime(8, 0),
        )
        anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_MISSING_MORNING_EXIT, message="Sortie matin manquante",
            employe=self.employe, site=self.site, date_pointage=date.today(),
        )

        response = self.client.post(self._url(anomalie), {
            'employe': self.employe.id, 'site': self.site.id,
            'date_pointage': date.today().isoformat(), 'periode': 'matin',
            'type_journee': 'normal', 'heure_arrivee': '08:00', 'heure_depart': '12:05',
            'statut': 'present', 'notes': '',
            'commentaire': "Sortie ajoutée manuellement après vérification.",
        }, follow=True)

        assert response.status_code == 200
        pointage_matin.refresh_from_db()
        assert pointage_matin.heure_depart == dtime(12, 5)

        anomalie.refresh_from_db()
        assert anomalie.statut == AnomaliePointage.STATUT_TRAITEE
        # La correction doit tracer précisément le changement réel
        corrections = anomalie.traitement.corrections
        heure_depart_diff = next((c for c in corrections if c['champ'] == 'heure_depart'), None)
        assert heure_depart_diff is not None
        assert heure_depart_diff['ancienne_valeur'] in (None, 'None')
        assert '12:05' in heure_depart_diff['nouvelle_valeur']

    def test_pointage_deja_correct_ne_produit_aucune_correction_vide(self):
        """Si l'admin ne change rien (juste un commentaire), la liste des
        corrections doit rester vide plutôt que remplie de faux positifs."""
        pointage = Pointage.objects.create(
            employe=self.employe, site=self.site, date_pointage=date.today(),
            periode='matin', type_journee='normal',
            heure_arrivee=dtime(8, 0), heure_depart=dtime(12, 0),
        )
        anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_MISSING_MORNING_EXIT, message="x",
            employe=self.employe, site=self.site, date_pointage=date.today(),
        )

        self.client.post(self._url(anomalie), {
            'employe': self.employe.id, 'site': self.site.id,
            'date_pointage': date.today().isoformat(), 'periode': 'matin',
            'type_journee': 'normal', 'heure_arrivee': '08:00', 'heure_depart': '12:00',
            'statut': 'present', 'notes': '',
            'commentaire': "Vérifié, pas de correction nécessaire, faux positif.",
        }, follow=True)

        anomalie.refresh_from_db()
        assert anomalie.traitement.corrections == []
        assert anomalie.statut == AnomaliePointage.STATUT_TRAITEE

    def test_anomalie_deja_cloturee_ne_peut_plus_etre_corrigee(self):
        anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK, message="x",
            employe=self.employe, date_pointage=date.today(),
        )
        anomalie.statut = AnomaliePointage.STATUT_CLOTUREE
        anomalie.save()

        response = self.client.get(self._url(anomalie))
        assert response.status_code == 302  # redirigé, pas de formulaire affiché
        assert Pointage.objects.count() == 0

    def test_process_scan_reste_inchange_par_ce_flux(self):
        """Garde-fou : la correction admin ne doit jamais passer par
        process_scan() ni par le moteur de décision — elle écrit
        directement le Pointage, comme toute correction manuelle RH."""
        import inspect
        from pointage import admin as admin_module
        source = inspect.getsource(admin_module.AnomaliePointageAdmin.corriger_pointage_view)
        assert 'process_scan' not in source
        assert 'DayStateMachine' not in source
        assert 'collect_day_context' not in source


class TestAtomiciteCorrectionRH(TestCase):
    """Une correction RH ne doit jamais être partiellement persistée.
    Si le traitement de l'anomalie échoue après form.save(), le Pointage
    et l'Anomalie doivent revenir exactement à leur état initial.
    """

    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username="admin_atomic", password="pass1234",
            role="admin", is_staff=True, is_superuser=True,
        )
        self.employe = Employe.objects.create(
            nom="Atomic", prenom="Test", matricule="AT001", actif=True,
        )
        self.site = Site.objects.create(
            nom="Site Atomic", adresse="1 rue Atomic",
            heure_ouverture_matin=dtime(8, 0), heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 0), heure_fermeture_apres_midi=dtime(17, 0),
        )
        self.pointage = Pointage.objects.create(
            employe=self.employe, site=self.site, date_pointage=date.today(),
            periode='matin', type_journee='normal', heure_arrivee=dtime(8, 0),
        )
        self.anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_MISSING_MORNING_EXIT,
            message="Sortie matin manquante", employe=self.employe,
            site=self.site, date_pointage=date.today(),
        )
        self.client = Client()
        self.client.force_login(self.admin)

    def test_correction_rollback_si_traitement_echoue(self):
        from unittest.mock import patch

        url = reverse('admin:anomalie_corriger_pointage', args=[self.anomalie.pk])
        with patch('pointage.admin.marquer_traitee', side_effect=RuntimeError('echec traitement')):
            self.client.post(url, {
                'employe': self.employe.id, 'site': self.site.id,
                'date_pointage': date.today().isoformat(), 'periode': 'matin',
                'type_journee': 'normal', 'heure_arrivee': '08:00',
                'heure_depart': '12:00', 'statut': 'present', 'notes': '',
                'commentaire': 'Correction test transactionnelle.',
            })

        self.pointage.refresh_from_db()
        self.anomalie.refresh_from_db()
        assert self.pointage.heure_depart is None
        assert self.anomalie.statut == AnomaliePointage.STATUT_OUVERTE
        assert not AnomalieTraitement.objects.filter(
            anomalie=self.anomalie
        ).exists()
