# pointage/tests/test_anomalies.py
#
# Tests de la couche de persistance des anomalies (Phase 4) :
# - AnomaliePointage : gravité dérivée, jamais stockée
# - anomalies.py : enregistrer_anomalie / marquer_traitee / marquer_cloturee

from datetime import date

from django.test import TestCase

from pointage.models import (
    AnomaliePointage, AnomalieTraitement, CustomUser, Employe, Site,
)
from pointage.anomalies import (
    enregistrer_anomalie, marquer_traitee, marquer_cloturee,
    compter_anomalies_ouvertes,
)


class TestGraviteDerivee(TestCase):
    """La gravité n'est jamais stockée : toujours recalculée depuis le type."""

    def test_gravite_correspond_aux_exemples_valides(self):
        cases = {
            AnomaliePointage.TYPE_DUPLICATE_SCAN: 'info',
            AnomaliePointage.TYPE_DURING_BREAK:   'warning',
            AnomaliePointage.TYPE_INVALID_QR:     'critique',
        }
        for type_anomalie, gravite_attendue in cases.items():
            anomalie = AnomaliePointage(type=type_anomalie, message="test")
            assert anomalie.gravite == gravite_attendue

    def test_gravite_absente_du_schema_stocke(self):
        """La gravité est une @property, pas un champ de modèle."""
        assert 'gravite' not in [f.name for f in AnomaliePointage._meta.get_fields()]

    def test_type_inconnu_retombe_sur_info(self):
        anomalie = AnomaliePointage(type='type_qui_nexiste_pas', message="test")
        assert anomalie.gravite == 'info'


class TestEnregistrerAnomalie(TestCase):
    def setUp(self):
        self.employe = Employe.objects.create(nom="Rakoto", prenom="Jean", matricule="E001", actif=True)
        self.site = Site.objects.create(
            nom="Site A", adresse="1 rue A",
            heure_ouverture_matin="08:00", heure_fermeture_matin="12:00",
            heure_ouverture_apres_midi="13:30", heure_fermeture_apres_midi="17:30",
        )

    def test_cree_une_anomalie_ouverte(self):
        anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK,
            message="Scan pendant la pause",
            employe=self.employe, site=self.site, date_pointage=date.today(),
        )
        assert anomalie.pk is not None
        assert anomalie.statut == AnomaliePointage.STATUT_OUVERTE
        assert anomalie.employe == self.employe

    def test_matricule_scanne_deduit_de_lemploye_si_absent(self):
        anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK, message="x", employe=self.employe,
        )
        assert anomalie.matricule_scanne == self.employe.matricule

    def test_employe_none_conserve_matricule_brut(self):
        """Cas QR invalide : aucun employé résolu, mais le matricule scanné
        est conservé pour traçabilité."""
        anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_INVALID_QR,
            message="QR invalide", matricule_scanne="E999",
        )
        assert anomalie.employe is None
        assert anomalie.matricule_scanne == "E999"

    def test_contexte_json_conserve(self):
        anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_DAY_COMPLETE, message="x",
            contexte={'scans_count': 4},
        )
        assert anomalie.contexte == {'scans_count': 4}


class TestCycleDeVie(TestCase):
    """ouverte -> traitee -> cloturee, et les transitions interdites."""

    def setUp(self):
        self.admin = CustomUser.objects.create(username="admin1", role="admin")
        self.anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_MISSING_MORNING_EXIT, message="Sortie matin manquante",
        )

    def test_marquer_traitee_change_statut_et_cree_trace(self):
        traitement = marquer_traitee(
            self.anomalie, self.admin, commentaire="Vérifié avec l'employé.",
        )
        self.anomalie.refresh_from_db()

        assert self.anomalie.statut == AnomaliePointage.STATUT_TRAITEE
        assert traitement.administrateur == self.admin
        assert traitement.commentaire == "Vérifié avec l'employé."
        assert AnomalieTraitement.objects.filter(anomalie=self.anomalie).count() == 1

    def test_marquer_traitee_conserve_les_corrections(self):
        corrections = [{
            'champ': 'heure_depart', 'ancienne_valeur': None, 'nouvelle_valeur': '12:05',
        }]
        traitement = marquer_traitee(
            self.anomalie, self.admin, commentaire="Correction manuelle.",
            corrections=corrections,
        )
        assert traitement.corrections == corrections

    def test_marquer_cloturee_necessite_traitement_prealable(self):
        with self.assertRaises(ValueError):
            marquer_cloturee(self.anomalie, self.admin)

        self.anomalie.refresh_from_db()
        assert self.anomalie.statut == AnomaliePointage.STATUT_OUVERTE

    def test_cycle_complet_ouverte_traitee_cloturee(self):
        marquer_traitee(self.anomalie, self.admin, commentaire="ok")
        self.anomalie.refresh_from_db()
        assert self.anomalie.statut == AnomaliePointage.STATUT_TRAITEE

        marquer_cloturee(self.anomalie, self.admin)
        self.anomalie.refresh_from_db()
        assert self.anomalie.statut == AnomaliePointage.STATUT_CLOTUREE
        assert self.anomalie.cloturee_par == self.admin
        assert self.anomalie.date_cloture is not None

    def test_impossible_de_retraiter_une_anomalie_cloturee(self):
        marquer_traitee(self.anomalie, self.admin, commentaire="ok")
        self.anomalie.refresh_from_db()
        marquer_cloturee(self.anomalie, self.admin)
        self.anomalie.refresh_from_db()

        with self.assertRaises(ValueError):
            marquer_traitee(self.anomalie, self.admin, commentaire="retraitement")

    def test_recloturer_une_anomalie_deja_cloturee_est_sans_effet(self):
        marquer_traitee(self.anomalie, self.admin, commentaire="ok")
        self.anomalie.refresh_from_db()
        marquer_cloturee(self.anomalie, self.admin)
        self.anomalie.refresh_from_db()
        date_cloture_initiale = self.anomalie.date_cloture

        marquer_cloturee(self.anomalie, self.admin)
        self.anomalie.refresh_from_db()
        assert self.anomalie.date_cloture == date_cloture_initiale


class TestCompterAnomaliesOuvertes(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create(username="admin2", role="admin")

    def test_compte_uniquement_les_ouvertes(self):
        a1 = enregistrer_anomalie(AnomaliePointage.TYPE_DURING_BREAK, message="1")
        a2 = enregistrer_anomalie(AnomaliePointage.TYPE_DURING_BREAK, message="2")
        enregistrer_anomalie(AnomaliePointage.TYPE_DURING_BREAK, message="3")

        marquer_traitee(a1, self.admin, commentaire="ok")
        a1.refresh_from_db()
        marquer_cloturee(a1, self.admin)
        marquer_traitee(a2, self.admin, commentaire="ok")

        assert compter_anomalies_ouvertes() == 1
