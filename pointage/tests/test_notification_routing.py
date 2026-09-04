from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.test import TestCase
from django.urls import reverse

from pointage.anomalies import enregistrer_anomalie
from pointage.models import AnomaliePointage


User = get_user_model()


class NotificationRoutingIsolationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="notif_admin",
            password="password123",
            role="admin",
            is_staff=True,
        )

    def test_web_notifications_ne_contiennent_jamais_un_lien_admin(self):
        enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK,
            message="Scan pendant la pause",
            date_pointage=date.today(),
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("notifications_api"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        for notification in data["notifications"]:
            self.assertNotIn("/admin/", notification.get("url", ""))

    @patch("pointage.web_notification_routing.views.notifications_api")
    def test_web_recrit_aussi_les_anciennes_urls_admin_des_demandes(self, mock_api):
        mock_api.return_value = JsonResponse({
            "notifications": [{
                "type": "demande_en_attente",
                "message": "Demande de modification",
                "url": "/admin/pointage/demandemodification/",
                "date": "2026-09-04T10:00:00+03:00",
            }],
            "count": 1,
        })
        self.client.force_login(self.admin)

        response = self.client.get(reverse("notifications_api"))

        self.assertEqual(response.status_code, 200)
        notification = response.json()["notifications"][0]
        self.assertEqual(notification["url"], reverse("pointages"))
        self.assertNotIn("/admin/", notification["url"])

    def test_jazzmin_notifications_utilisent_le_endpoint_admin_separe(self):
        anomalie = enregistrer_anomalie(
            AnomaliePointage.TYPE_DURING_BREAK,
            message="Scan pendant la pause",
            date_pointage=date.today(),
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("admin_notifications_api"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        anomaly_notifications = [
            n for n in data["notifications"] if n.get("type") == "anomalie"
        ]
        self.assertTrue(anomaly_notifications)
        self.assertEqual(
            anomaly_notifications[0]["url"],
            f"/admin/pointage/anomaliepointage/{anomalie.pk}/workflow/",
        )
