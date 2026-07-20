# pointage/tests/test_services.py
#
# TESTS D'INTÉGRATION DE LA PHASE 3
# ==================================
#
# Vérifie que process_scan() -> collect_day_context() -> DayStateMachine
# -> _apply_scan_decision() produit le bon résultat en base, notamment :
#   - le bug d'origine (premier scan à 14h41 = entrée après-midi, sans
#     créer de faux pointage matin) est bien corrigé ;
#   - les règles métier de la spec (sortie matin manquante, pause, journée
#     terminée, sortie tardive toujours autorisée) sont respectées de bout
#     en bout, écriture en base comprise ;
#   - le site est fixé à l'entrée d'une période et ne change pas à la sortie.

from datetime import time as dtime, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from pointage.models import Employe, Site, Pointage, Scan
from pointage.services import process_scan


def _aware(date_, hh, mm):
    """Construit un datetime aware pour l'heure locale donnée, aujourd'hui."""
    return timezone.make_aware(
        timezone.datetime.combine(date_, dtime(hh, mm))
    )


class ScanServiceTestCase(TestCase):
    """Base commune : un employé et un site aux horaires standards."""

    def setUp(self):
        self.site = Site.objects.create(
            nom="Site Principal",
            adresse="1 Rue de Test",
            heure_ouverture_matin=dtime(8, 0),
            heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 30),
            heure_fermeture_apres_midi=dtime(17, 30),
        )
        self.autre_site = Site.objects.create(
            nom="Site Secondaire",
            adresse="2 Rue de Test",
            heure_ouverture_matin=dtime(8, 0),
            heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 30),
            heure_fermeture_apres_midi=dtime(17, 30),
        )
        self.employe = Employe.objects.create(
            nom="Rakoto", prenom="Jean", matricule="E001", actif=True
        )
        self.today = timezone.localtime(timezone.now()).date()

    def _scan(self, hh, mm, site=None):
        """Effectue un scan à l'heure donnée (aujourd'hui), site par défaut."""
        site = site or self.site
        fake_now = _aware(self.today, hh, mm)
        with patch('pointage.services.timezone.now', return_value=fake_now):
            return process_scan(
                matricule=self.employe.matricule,
                qr_token=str(self.employe.qr_code_token),
                site_id=site.id,
            )


class TestBugOriginePremierScanApresMidi(ScanServiceTestCase):
    """LE bug qui a motivé la refonte : premier scan à 14h41."""

    def test_premier_scan_14h41_devient_entree_apres_midi(self):
        result = self._scan(14, 41)

        assert result['status'] == 'success'
        assert result['code'] == 'entree_apres_midi'
        assert "Le matin sera considéré comme absent" in result['message']

    def test_aucun_faux_pointage_matin_cree(self):
        self._scan(14, 41)

        assert Pointage.objects.filter(
            employe=self.employe, periode='matin'
        ).count() == 0

        pointage_am = Pointage.objects.get(
            employe=self.employe, periode='apres_midi'
        )
        assert pointage_am.heure_arrivee == dtime(14, 41)
        assert pointage_am.heure_depart is None

    def test_absence_matin_visible_uniquement_via_calcul_rh(self):
        """L'absence matin n'est jamais un pointage : elle se déduit de
        l'absence de ligne, pas d'un flag stocké."""
        self._scan(14, 41)

        statut = self.employe.get_statut_journee(self.today)
        assert statut['matin']['present'] is False
        assert statut['apres_midi']['present'] is True


class TestSequenceComplete(ScanServiceTestCase):
    """Journée normale complète : E1 -> S1 -> E2 -> S2."""

    def test_sequence_complete_journee_normale(self):
        r1 = self._scan(8, 0)
        assert r1['status'] == 'success' and r1['code'] == 'entree_matin'

        r2 = self._scan(12, 0)
        assert r2['status'] == 'success' and r2['code'] == 'sortie_matin'

        r3 = self._scan(13, 30)
        assert r3['status'] == 'success' and r3['code'] == 'entree_apres_midi'

        r4 = self._scan(17, 30)
        assert r4['status'] == 'success' and r4['code'] == 'sortie_apres_midi'

        pm = Pointage.objects.get(employe=self.employe, periode='matin')
        pam = Pointage.objects.get(employe=self.employe, periode='apres_midi')
        assert pm.heure_arrivee == dtime(8, 0) and pm.heure_depart == dtime(12, 0)
        assert pam.heure_arrivee == dtime(13, 30) and pam.heure_depart == dtime(17, 30)

    def test_journee_terminee_refuse_scan_supplementaire(self):
        self._scan(8, 0)
        self._scan(12, 0)
        self._scan(13, 30)
        self._scan(17, 30)

        r5 = self._scan(17, 45)

        assert r5['status'] == 'warning'
        assert r5['code'] == 'day_complete'
        # Aucune écriture supplémentaire
        assert Pointage.objects.filter(employe=self.employe).count() == 2


class TestReglesMetier(ScanServiceTestCase):
    """Règles explicites de la spec, vérifiées de bout en bout."""

    def test_sortie_matin_oubliee_bloque_entree_apres_midi(self):
        self._scan(8, 0)  # entrée matin seulement, pas de sortie

        r = self._scan(14, 0)

        assert r['status'] == 'warning'
        assert r['code'] == 'missing_morning_exit'
        # Le pointage matin n'est pas modifié, aucun pointage après-midi créé
        pm = Pointage.objects.get(employe=self.employe, periode='matin')
        assert pm.heure_depart is None
        assert Pointage.objects.filter(
            employe=self.employe, periode='apres_midi'
        ).count() == 0

    def test_scan_pendant_la_pause_refuse(self):
        r = self._scan(12, 30)

        assert r['status'] == 'warning'
        assert r['code'] == 'during_break'
        assert Pointage.objects.filter(employe=self.employe).count() == 0

    def test_sortie_tardive_toujours_autorisee(self):
        """Régression Bug A : une sortie à 18h30 (heures sup./urgence) doit
        être acceptée, pas bloquée par le filtre global d'heures du site."""
        self._scan(13, 30)  # entrée après-midi

        r = self._scan(18, 30)

        assert r['status'] == 'success'
        assert r['code'] == 'sortie_apres_midi'
        assert "après les heures de fermeture" in r['message']

        pam = Pointage.objects.get(employe=self.employe, periode='apres_midi')
        assert pam.heure_depart == dtime(18, 30)

    def test_double_scan_rapide_refuse(self):
        r1 = self._scan(8, 0)
        assert r1['status'] == 'success'

        # Rescan 30 secondes plus tard (< seuil anti-doublon de 120s)
        fake_now = _aware(self.today, 8, 0) + timedelta(seconds=30)
        with patch('pointage.services.timezone.now', return_value=fake_now):
            r2 = process_scan(
                matricule=self.employe.matricule,
                qr_token=str(self.employe.qr_code_token),
                site_id=self.site.id,
            )

        assert r2['status'] == 'warning'
        assert r2['code'] == 'DOUBLON'
        assert Pointage.objects.filter(employe=self.employe).count() == 1


class TestSiteFixeALEntree(ScanServiceTestCase):
    """Le site est fixé à l'entrée d'une période et ne change pas à la sortie."""

    def test_site_entree_conserve_a_la_sortie_meme_site_different(self):
        self._scan(8, 0, site=self.site)

        # Sortie scannée depuis un autre site (ex: badge oublié, dépannage)
        self._scan(12, 0, site=self.autre_site)

        pm = Pointage.objects.get(employe=self.employe, periode='matin')
        assert pm.site_id == self.site.id  # inchangé : site de l'entrée

    def test_changement_de_site_autorise_entre_matin_et_apres_midi(self):
        self._scan(8, 0, site=self.site)
        self._scan(12, 0, site=self.site)
        self._scan(13, 30, site=self.autre_site)

        pm = Pointage.objects.get(employe=self.employe, periode='matin')
        pam = Pointage.objects.get(employe=self.employe, periode='apres_midi')
        assert pm.site_id == self.site.id
        assert pam.site_id == self.autre_site.id


# ============================================================
# PHASE 4 — anomalies enregistrées en effet de bord
# ============================================================
#
# Chaque scénario de refus déjà couvert plus haut (Phase 3) doit
# désormais AUSSI créer une AnomaliePointage correspondante, sans que
# la réponse de process_scan() ne change (mêmes assertions status/code/
# message que dans les classes ci-dessus).

from pointage.models import AnomaliePointage


class TestAnomaliesEnregistreesPourLesRefusDeDecision(ScanServiceTestCase):
    """Anomalies issues de _apply_scan_decision() (decision.allowed=False)."""

    def test_sortie_matin_oubliee_cree_une_anomalie(self):
        self._scan(8, 0)
        self._scan(14, 0)  # refusé : missing_morning_exit

        anomalie = AnomaliePointage.objects.get(employe=self.employe)
        assert anomalie.type == AnomaliePointage.TYPE_MISSING_MORNING_EXIT
        assert anomalie.statut == AnomaliePointage.STATUT_OUVERTE
        assert anomalie.site_id == self.site.id
        assert anomalie.date_pointage == self.today

    def test_scan_pendant_pause_cree_une_anomalie(self):
        self._scan(12, 30)

        anomalie = AnomaliePointage.objects.get(employe=self.employe)
        assert anomalie.type == AnomaliePointage.TYPE_DURING_BREAK
        assert anomalie.gravite == 'warning'

    def test_journee_terminee_cree_une_anomalie(self):
        self._scan(8, 0); self._scan(12, 0); self._scan(13, 30); self._scan(17, 30)
        self._scan(17, 45)

        anomalie = AnomaliePointage.objects.filter(
            employe=self.employe, type=AnomaliePointage.TYPE_DAY_COMPLETE
        ).get()
        assert anomalie.gravite == 'info'

    def test_sortie_tardive_autorisee_ne_cree_aucune_anomalie(self):
        """Un scan accepté (même avec un avertissement métier) n'est pas
        une anomalie : seuls les refus (decision.allowed=False) le sont."""
        self._scan(13, 30)
        self._scan(18, 30)  # sortie tardive, acceptée

        assert AnomaliePointage.objects.filter(employe=self.employe).count() == 0

    def test_scan_reussi_ne_cree_aucune_anomalie(self):
        self._scan(8, 0)
        assert AnomaliePointage.objects.count() == 0


class TestAnomaliesEnregistreesPourLesPreControles(ScanServiceTestCase):
    """Anomalies issues de process_scan() lui-même, avant la machine à états."""

    def test_qr_invalide_cree_une_anomalie_sans_employe_resolu(self):
        fake_now = _aware(self.today, 9, 0)
        with patch('pointage.services.timezone.now', return_value=fake_now):
            result = process_scan(
                matricule="INCONNU", qr_token="00000000-0000-0000-0000-000000000000",
                site_id=self.site.id,
            )

        assert result['status'] == 'error'
        assert result['code'] == 'QR_INVALIDE'

        anomalie = AnomaliePointage.objects.get(type=AnomaliePointage.TYPE_INVALID_QR)
        assert anomalie.employe is None
        assert anomalie.matricule_scanne == "INCONNU"
        assert anomalie.gravite == 'critique'

    def test_employe_inactif_cree_une_anomalie_distincte_du_qr_invalide(self):
        employe_inactif = Employe.objects.create(
            nom="Rasoa", prenom="Marie", matricule="E002", actif=False
        )
        fake_now = _aware(self.today, 9, 0)
        with patch('pointage.services.timezone.now', return_value=fake_now):
            result = process_scan(
                matricule=employe_inactif.matricule,
                qr_token=str(employe_inactif.qr_code_token),
                site_id=self.site.id,
            )

        assert result['status'] == 'error'

        anomalie = AnomaliePointage.objects.get(type=AnomaliePointage.TYPE_EMPLOYE_INACTIF)
        assert anomalie.employe == employe_inactif
        # Bien une anomalie distincte de QR invalide, même statut HTTP/erreur
        assert AnomaliePointage.objects.filter(type=AnomaliePointage.TYPE_INVALID_QR).count() == 0

    def test_site_invalide_cree_une_anomalie(self):
        fake_now = _aware(self.today, 9, 0)
        with patch('pointage.services.timezone.now', return_value=fake_now):
            result = process_scan(
                matricule=self.employe.matricule,
                qr_token=str(self.employe.qr_code_token),
                site_id=999999,
            )

        assert result['status'] == 'error'
        anomalie = AnomaliePointage.objects.get(type=AnomaliePointage.TYPE_SITE_INVALIDE)
        assert anomalie.employe == self.employe

    def test_double_scan_cree_une_anomalie_avec_contexte(self):
        self._scan(8, 0)
        fake_now = _aware(self.today, 8, 0) + timedelta(seconds=30)
        with patch('pointage.services.timezone.now', return_value=fake_now):
            process_scan(
                matricule=self.employe.matricule,
                qr_token=str(self.employe.qr_code_token),
                site_id=self.site.id,
            )

        anomalie = AnomaliePointage.objects.get(type=AnomaliePointage.TYPE_DUPLICATE_SCAN)
        assert 'dernier_scan_id' in anomalie.contexte
