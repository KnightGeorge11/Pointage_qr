from datetime import time as dtime
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pointage.models import Employe, Site, Pointage, AnomaliePointage, CustomUser
from pointage.services import process_scan


def _aware(date_, hh, mm):
    return timezone.make_aware(timezone.datetime.combine(date_, dtime(hh, mm)))


class ScannerSortieAnticipeeWebTestCase(TestCase):
    def setUp(self):
        self.site = Site.objects.create(
            nom="Site Principal",
            adresse="1 Rue de Test",
            heure_ouverture_matin=dtime(8, 0),
            heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 30),
            heure_fermeture_apres_midi=dtime(17, 30),
        )
        self.employe = Employe.objects.create(
            nom="Rakoto", prenom="Jean", matricule="E-WEB-001", actif=True
        )
        self.user = CustomUser.objects.create_user(
            username="scanner-web-test", password="test-password", role="user"
        )
        self.client.force_login(self.user)
        self.today = timezone.localtime(timezone.now()).date()

        entree = _aware(self.today, 8, 0)
        with patch('pointage.services.timezone.now', return_value=entree):
            result = process_scan(
                matricule=self.employe.matricule,
                qr_token=str(self.employe.qr_code_token),
                site_id=self.site.id,
            )
        assert result['status'] == 'success'

    def test_sortie_anticipee_affiche_ecran_avant_enregistrement(self):
        fake_now = _aware(self.today, 11, 0)
        with patch('pointage.scanner_anticipation.timezone.now', return_value=fake_now):
            response = self.client.post(reverse('scanner'), {
                'matricule': self.employe.matricule,
                'site_id': self.site.id,
                'periode_type': 'auto',
            })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sortie anticipée détectée')
        self.assertContains(response, '60 min')
        self.assertContains(response, 'Motif de votre sortie')
        self.assertFalse(
            Pointage.objects.filter(employe=self.employe, periode='matin', heure_depart__isnull=False).exists()
        )

    def test_confirmation_enregistre_heure_reelle_et_motif_en_attente(self):
        fake_scan = _aware(self.today, 11, 0)
        with patch('pointage.scanner_anticipation.timezone.now', return_value=fake_scan):
            first = self.client.post(reverse('scanner'), {
                'matricule': self.employe.matricule,
                'site_id': self.site.id,
                'periode_type': 'auto',
            })
        self.assertEqual(first.status_code, 200)

        fake_confirm = _aware(self.today, 11, 1)
        with patch('pointage.services.timezone.now', return_value=fake_confirm), \
             patch('pointage.scanner_anticipation.timezone.now', return_value=fake_confirm):
            response = self.client.post(reverse('scanner_confirmer_sortie_anticipee'), {
                'motif': 'Rendez-vous médical',
            })

        self.assertRedirects(response, reverse('scanner'))
        pointage = Pointage.objects.get(employe=self.employe, periode='matin')
        self.assertEqual(pointage.heure_depart, dtime(11, 1))

        anomalie = AnomaliePointage.objects.get(
            employe=self.employe,
            type=AnomaliePointage.TYPE_DEPART_ANTICIPE,
        )
        self.assertEqual(anomalie.contexte['motif_employe'], 'Rendez-vous médical')
        self.assertEqual(anomalie.contexte['autorisation_rh'], 'en_attente')
        self.assertEqual(anomalie.contexte['pointage_id'], pointage.id)

    def test_motif_vide_n_enregistre_pas_le_pointage(self):
        fake_now = _aware(self.today, 11, 0)
        with patch('pointage.scanner_anticipation.timezone.now', return_value=fake_now):
            self.client.post(reverse('scanner'), {
                'matricule': self.employe.matricule,
                'site_id': self.site.id,
                'periode_type': 'auto',
            })

        response = self.client.post(reverse('scanner_confirmer_sortie_anticipee'), {'motif': ' '})
        self.assertRedirects(response, reverse('scanner'))
        self.assertIsNone(
            Pointage.objects.get(employe=self.employe, periode='matin').heure_depart
        )
