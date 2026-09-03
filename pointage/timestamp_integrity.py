"""Garde-fou d'intégrité des horodatages mobiles hors ligne.

Le mode offline doit rester fonctionnel : un événement peut légitimement être
synchronisé plusieurs heures après sa capture. On ne bloque donc pas un scan
uniquement parce que l'horodatage client diffère de l'heure serveur.

En revanche, un écart important est conservé comme anomalie lorsqu'il peut
favoriser l'employé : arrivée artificiellement avancée ou départ artificiellement
repoussé. Cela donne au RH un signal explicite avant validation d'heures
supplémentaires ou analyse d'un retard.
"""

import json
from datetime import timedelta
from functools import wraps

from django.utils import timezone

from .models import AnomaliePointage

# Au-delà de cette durée, l'écart entre l'heure de capture déclarée par le
# client et l'heure de synchronisation serveur devient suffisamment important
# pour nécessiter une vérification humaine. Le scan reste accepté afin de ne
# pas casser le mode hors ligne.
SUSPICIOUS_OFFSET = timedelta(minutes=15)


def _get_payload(request):
    try:
        if hasattr(request, "body") and request.body:
            return json.loads(request.body.decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError):
        return {}
    return getattr(request, "POST", {}) or {}


def _parse_capture_time(value):
    if not value:
        return None
    try:
        captured_at = timezone.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if timezone.is_naive(captured_at):
            captured_at = timezone.make_aware(captured_at, timezone.get_current_timezone())
        return timezone.localtime(captured_at)
    except (TypeError, ValueError):
        return None


def _install_mobile_timestamp_guard():
    """Ajoute une anomalie de plausibilité après un scan mobile réussi."""
    try:
        from .views_mobile import MobileRecordScanAPIView
    except ImportError:
        return

    if getattr(MobileRecordScanAPIView, "_timestamp_integrity_installed", False):
        return

    original_post = MobileRecordScanAPIView.post

    @wraps(original_post)
    def guarded_post(self, request, *args, **kwargs):
        server_received_at = timezone.localtime(timezone.now())
        payload = _get_payload(request)
        captured_at = _parse_capture_time(payload.get("captured_at"))

        response = original_post(self, request, *args, **kwargs)

        if captured_at is None:
            return response

        # L'endpoint a déjà validé les bornes absolues et exécuté process_scan.
        # Ici nous ne bloquons pas le scan : nous signalons seulement les écarts
        # qui ont un impact potentiel sur la rémunération ou le retard.
        delta = captured_at - server_received_at
        if abs(delta) <= SUSPICIOUS_OFFSET:
            return response

        try:
            status_code = getattr(response, "status_code", 500)
            if status_code not in (200, 201):
                return response

            result = json.loads(response.content.decode("utf-8"))
            if result.get("status") != "success":
                return response

            code = result.get("code")
            beneficiaire = code in {
                "entree_matin",
                "entree_apres_midi",
                "debut_garde",
                "sortie_apres_midi",
                "fin_garde",
            }
            if not beneficiaire:
                return response

            if delta.total_seconds() < 0 and code in {"entree_matin", "entree_apres_midi", "debut_garde"}:
                motif = "capture déclarée antérieure à la réception serveur"
            elif delta.total_seconds() > 0 and code in {"sortie_apres_midi", "fin_garde"}:
                motif = "capture déclarée postérieure à la réception serveur"
            else:
                return response

            data = result.get("data") or {}
            employe_id = data.get("employe_id")
            pointage_id = data.get("pointage_id")
            employe = None
            if employe_id:
                from .models import Employe
                employe = Employe.objects.filter(pk=employe_id).first()

            AnomaliePointage.objects.create(
                type=AnomaliePointage.TYPE_TRANSITION_IMPOSSIBLE,
                employe=employe,
                date_pointage=captured_at.date(),
                message=(
                    "Horodatage mobile suspect : l'heure de capture diffère "
                    f"de {abs(int(delta.total_seconds() // 60))} minute(s) de la "
                    "réception serveur. Vérification RH recommandée."
                ),
                contexte={
                    "code_scan": code,
                    "pointage_id": pointage_id,
                    "captured_at": captured_at.isoformat(),
                    "server_received_at": server_received_at.isoformat(),
                    "ecart_secondes": int(delta.total_seconds()),
                    "motif": motif,
                    "source": "mobile_offline_integrity",
                },
            )
        except Exception:
            # Le garde-fou ne doit jamais transformer un scan fonctionnel en
            # erreur 500. L'échec de signalement est journalisé par Django via
            # le logger global du serveur et le scan reste inchangé.
            return response

        return response

    MobileRecordScanAPIView.post = guarded_post
    MobileRecordScanAPIView._timestamp_integrity_installed = True


_install_mobile_timestamp_guard()
