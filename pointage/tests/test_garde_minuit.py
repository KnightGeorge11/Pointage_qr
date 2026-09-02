# pointage/tests/test_garde_minuit.py
#
# GARDE DE NUIT TRAVERSANT MINUIT (Phase 10/28)
# ===============================================
# Vérifie que process_scan(mode='garde') gère correctement :
#   - une garde qui commence un jour et se termine le lendemain ;
#   - le renseignement de date_depart (pas seulement heure_depart) ;
#   - le calcul correct des heures travaillées à travers minuit ;
#   - force_new sur une garde déjà en cours le même jour civil
#     (IntegrityError documentée, cf. audit Phase 4/9).
from datetime import time as dtime, timedelta, date

from django.test import TestCase
from django.utils import timezone

from pointage.models import Employe, Site, Pointage
from pointage.services import process_scan


def _aware(date_, hh, mm):
    return timezone.make_aware(timezone.datetime.combine(date_, dtime(hh, mm)))


class GardeTraversantMinuitTestCase(TestCase):
    def setUp(self):
        self.site = Site.objects.create(
            nom="Site Garde", adresse="1 Rue de Test",
            heure_ouverture_matin=dtime(8, 0), heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 0), heure_fermeture_apres_midi=dtime(17, 0),
        )
        self.employe = Employe.objects.create(
            nom="Nuit", prenom="Garde", matricule="GARDE01",
            qr_code_token="11111111-1111-1111-1111-111111111111", actif=True,
        )

    def _debut_garde(self, jour, hh, mm):
        if not Pointage.objects.filter(employe=self.employe, date_pointage=jour, periode="nuit", type_journee="garde", heure_arrivee__isnull=True, heure_depart__isnull=True).exists():
            Pointage.objects.create(employe=self.employe, site=self.site, date_pointage=jour, periode="nuit", type_journee="garde", statut="absent")
        now = _aware(jour, hh, mm)
        with __import__('unittest.mock', fromlist=['patch']).patch('pointage.services.timezone.now', return_value=now):
            return process_scan(
                matricule=self.employe.matricule,
                qr_token=str(self.employe.qr_code_token),
                site_id=self.site.id, mode='garde',
            )

    def test_garde_20h_a_06h_le_lendemain(self):
        result_debut = self._debut_garde(date(2026, 8, 10), 20, 0)
        assert result_debut['status'] == 'success'
        assert result_debut['code'] == 'debut_garde'

        result_fin = self._debut_garde(date(2026, 8, 11), 6, 0)
        assert result_fin['status'] == 'success'
        assert result_fin['code'] == 'fin_garde'

        pointage = Pointage.objects.get(employe=self.employe, periode='nuit')
        assert pointage.date_pointage == date(2026, 8, 10)
        assert pointage.heure_arrivee == dtime(20, 0)
        assert pointage.heure_depart == dtime(6, 0)
        # Phase 10 : date_depart doit être réellement renseignée
        assert pointage.date_depart == date(2026, 8, 11)

    def test_garde_22h_a_07h_calcule_9h_travaillees(self):
        self._debut_garde(date(2026, 8, 10), 22, 0)
        self._debut_garde(date(2026, 8, 11), 7, 0)

        pointage = Pointage.objects.get(employe=self.employe, periode='nuit')
        pointage.calculer_heures_travaillees()
        assert pointage.heures_travaillees == timedelta(hours=9)

    def test_garde_23h_a_05h_calcule_6h_travaillees(self):
        self._debut_garde(date(2026, 8, 10), 23, 0)
        self._debut_garde(date(2026, 8, 11), 5, 0)

        pointage = Pointage.objects.get(employe=self.employe, periode='nuit')
        pointage.calculer_heures_travaillees()
        assert pointage.heures_travaillees == timedelta(hours=6)

    def test_force_new_sur_garde_deja_en_cours_le_meme_jour_ferme_la_garde_au_lieu_de_planter(self):
        """
        Phase 9 (correctif) : force_new=True alors qu'une garde est déjà en
        cours LE MÊME JOUR CIVIL ne doit plus lever d'IntegrityError. Une
        garde du jour même déjà ouverte est toujours fermée normalement —
        force_new ne s'applique qu'aux gardes oubliées d'un jour précédent.
        """
        jour = date(2026, 8, 10)
        self._debut_garde(jour, 20, 0)  # garde en cours, pas encore fermée

        now = _aware(jour, 21, 0)
        from unittest.mock import patch
        with patch('pointage.services.timezone.now', return_value=now):
            result = process_scan(
                matricule=self.employe.matricule,
                qr_token=str(self.employe.qr_code_token),
                site_id=self.site.id, mode='garde', force_new_garde=True,
            )

        assert result['status'] == 'success'
        assert result['code'] == 'fin_garde'
        assert Pointage.objects.filter(employe=self.employe, periode='nuit').count() == 1

    def test_force_new_refuse_si_une_garde_anterieure_reste_ouverte(self):
        """
        Usage prévu de force_new : une garde d'un jour PRÉCÉDENT, jamais
        fermée (oubliée), ne doit pas empêcher de démarrer une garde
        aujourd'hui. force_new l'ignore et une nouvelle garde est créée.
        """
        avant_hier = date(2026, 8, 8)
        self._debut_garde(avant_hier, 20, 0)  # jamais fermée (oubliée)

        aujourdhui = date(2026, 8, 10)
        now = _aware(aujourdhui, 20, 0)
        from unittest.mock import patch
        with patch('pointage.services.timezone.now', return_value=now):
            result = process_scan(
                matricule=self.employe.matricule,
                qr_token=str(self.employe.qr_code_token),
                site_id=self.site.id, mode='garde', force_new_garde=True,
            )

        assert result['status'] == 'warning'
        assert result['code'] == 'GARDE_PRECEDENTE_NON_CLOTUREE'
        assert Pointage.objects.filter(employe=self.employe, periode='nuit').count() == 1
        vieille = Pointage.objects.get(employe=self.employe, periode='nuit', date_pointage=avant_hier)
        assert vieille.heure_depart is None

    def test_deuxieme_garde_distincte_meme_jour_refusee_proprement(self):
        """
        Cas E de l'audit : un employé termine une première garde, puis en
        démarre une deuxième distincte le MÊME jour civil (ex: rappel
        d'urgence). La contrainte unique (employe, date_pointage, periode)
        empêche de créer un deuxième Pointage 'nuit' ce jour-là — le
        service doit refuser proprement (warning + anomalie tracée) plutôt
        que de laisser un IntegrityError remonter en erreur serveur, et la
        première garde (déjà close) ne doit pas être touchée.
        """
        jour = date(2026, 8, 20)
        self._debut_garde(jour, 20, 0)
        now_fin = _aware(jour, 23, 0)
        from unittest.mock import patch
        with patch('pointage.services.timezone.now', return_value=now_fin):
            process_scan(
                matricule=self.employe.matricule,
                qr_token=str(self.employe.qr_code_token),
                site_id=self.site.id, mode='garde',
            )
        assert Pointage.objects.filter(employe=self.employe, periode='nuit', date_pointage=jour).count() == 1
        premiere_garde = Pointage.objects.get(employe=self.employe, periode='nuit', date_pointage=jour)
        assert premiere_garde.heure_depart == dtime(23, 0)

        # Rappel d'urgence le même jour, > 120s après la fin de la garde 1
        now_rappel = _aware(jour, 23, 5)
        with patch('pointage.services.timezone.now', return_value=now_rappel):
            result = process_scan(
                matricule=self.employe.matricule,
                qr_token=str(self.employe.qr_code_token),
                site_id=self.site.id, mode='garde',
            )

        assert result['status'] == 'warning'
        assert result['code'] == 'GARDE_MULTIPLE_NON_SUPPORTEE'
        # Aucun doublon créé, la première garde reste intacte
        assert Pointage.objects.filter(employe=self.employe, periode='nuit', date_pointage=jour).count() == 1
        premiere_garde.refresh_from_db()
        assert premiere_garde.heure_depart == dtime(23, 0)
