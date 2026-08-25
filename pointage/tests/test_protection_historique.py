# pointage/tests/test_protection_historique.py
#
# PROTECTION DE L'HISTORIQUE (Point 3)
# =====================================
# Pointage.employe/site et Scan.employe/site sont en PROTECT (pas CASCADE) :
# un Employe ou un Site avec de l'historique ne doit jamais pouvoir être
# supprimé silencieusement en emportant tout son historique avec lui.
from datetime import time as dtime, date

from django.test import TestCase
from django.db.models import ProtectedError
from django.utils import timezone

from pointage.models import Employe, Site, Pointage, Scan


class ProtectionHistoriqueTestCase(TestCase):
    def setUp(self):
        self.site = Site.objects.create(
            nom="Site Protégé", adresse="1 Rue Test",
            heure_ouverture_matin=dtime(8, 0), heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 0), heure_fermeture_apres_midi=dtime(17, 0),
        )
        self.employe = Employe.objects.create(
            nom="Protégé", prenom="Historique", matricule="PROT01", actif=True,
        )
        self.pointage = Pointage.objects.create(
            employe=self.employe, site=self.site, date_pointage=date.today(),
            periode='matin', type_journee='normal', heure_arrivee=dtime(8, 5),
        )
        self.scan = Scan.objects.create(
            employe=self.employe, site=self.site,
            timestamp=timezone.now(), type_scan='entree_matin',
        )

    def test_suppression_employe_avec_historique_est_bloquee(self):
        with self.assertRaises(ProtectedError):
            self.employe.delete()
        # L'historique doit toujours exister après la tentative
        assert Pointage.objects.filter(pk=self.pointage.pk).exists()
        assert Scan.objects.filter(pk=self.scan.pk).exists()

    def test_suppression_site_avec_historique_est_bloquee(self):
        with self.assertRaises(ProtectedError):
            self.site.delete()
        assert Pointage.objects.filter(pk=self.pointage.pk).exists()
        assert Scan.objects.filter(pk=self.scan.pk).exists()

    def test_desactivation_employe_reste_possible(self):
        """La désactivation (actif=False) est la voie normale, jamais bloquée."""
        self.employe.actif = False
        self.employe.save()
        self.employe.refresh_from_db()
        assert self.employe.actif is False
        assert Pointage.objects.filter(pk=self.pointage.pk).exists()

    def test_suppression_employe_sans_historique_fonctionne(self):
        """PROTECT ne doit bloquer que s'il y a réellement un historique."""
        employe_sans_historique = Employe.objects.create(
            nom="Sans", prenom="Historique", matricule="VIDE01", actif=True,
        )
        employe_sans_historique.delete()
        assert not Employe.objects.filter(matricule="VIDE01").exists()
