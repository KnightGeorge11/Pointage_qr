from datetime import time as dtime
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone

from pointage.models import Employe, Site, Scan, Pointage
from pointage.services import process_scan


class OfflineIdempotencyTestCase(TestCase):
    def setUp(self):
        self.site = Site.objects.create(
            nom="Site Offline",
            adresse="1 Rue Test",
            heure_ouverture_matin=dtime(8, 0),
            heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 30),
            heure_fermeture_apres_midi=dtime(17, 30),
        )
        self.employe = Employe.objects.create(
            nom="Rakoto", prenom="Jean", matricule="OFF001", actif=True
        )
        self.date = timezone.localdate()

    def _captured_at(self, hour, minute):
        return timezone.make_aware(
            timezone.datetime.combine(self.date, dtime(hour, minute))
        )

    def test_rejeu_meme_evenement_est_idempotent(self):
        event_id = uuid4()
        captured_at = self._captured_at(8, 0)

        first = process_scan(
            matricule=self.employe.matricule,
            qr_token=str(self.employe.qr_code_token),
            site_id=self.site.id,
            client_event_id=event_id,
            captured_at=captured_at,
        )
        second = process_scan(
            matricule=self.employe.matricule,
            qr_token=str(self.employe.qr_code_token),
            site_id=self.site.id,
            client_event_id=event_id,
            captured_at=captured_at,
        )

        self.assertEqual(first["status"], "success")
        self.assertEqual(first["code"], "entree_matin")
        self.assertTrue(second["idempotent"])
        self.assertEqual(second["code"], "entree_matin")
        self.assertEqual(
            Scan.objects.filter(client_event_id=event_id).count(), 1
        )
        self.assertEqual(
            Pointage.objects.filter(
                employe=self.employe, date_pointage=self.date, periode="matin"
            ).count(),
            1,
        )

    def test_evenements_distincts_ne_sont_pas_idempotents(self):
        first_id = uuid4()
        second_id = uuid4()
        captured_at = self._captured_at(8, 0)

        first = process_scan(
            matricule=self.employe.matricule,
            qr_token=str(self.employe.qr_code_token),
            site_id=self.site.id,
            client_event_id=first_id,
            captured_at=captured_at,
        )
        second = process_scan(
            matricule=self.employe.matricule,
            qr_token=str(self.employe.qr_code_token),
            site_id=self.site.id,
            client_event_id=second_id,
            captured_at=captured_at,
        )

        self.assertEqual(first["status"], "success")
        self.assertEqual(second["status"], "warning")
        self.assertEqual(second["code"], "DOUBLON")
        self.assertEqual(Scan.objects.filter(employe=self.employe).count(), 1)

    def test_captured_at_determine_lheure_metier(self):
        event_id = uuid4()
        captured_at = self._captured_at(14, 41)

        result = process_scan(
            matricule=self.employe.matricule,
            qr_token=str(self.employe.qr_code_token),
            site_id=self.site.id,
            client_event_id=event_id,
            captured_at=captured_at,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["code"], "entree_apres_midi")
        pointage = Pointage.objects.get(
            employe=self.employe, date_pointage=self.date, periode="apres_midi"
        )
        self.assertEqual(pointage.heure_arrivee, dtime(14, 41))
        scan = Scan.objects.get(client_event_id=event_id)
        self.assertEqual(scan.timestamp, captured_at)
