"""Flux Web de sortie anticipée.

Ce module enveloppe le scanner Web existant sans modifier son comportement pour
les scans ordinaires. Lorsqu'une sortie anticipée est détectée, le pointage
n'est pas encore écrit : l'employé doit d'abord fournir son motif et confirmer.
Après confirmation, process_scan() reste l'unique moteur d'écriture du pointage.
"""

from datetime import datetime
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from . import views
from .context import collect_day_context
from .domain import ScanActionType
from .models import AnomaliePointage, Employe, Site
from .services import parse_qr_data, process_scan
from .state_machine import DayStateMachine

PENDING_SESSION_KEY = "scanner_sortie_anticipee_pending"


def _resolve_scan_identity(raw_qr: str, matricule: str):
    if raw_qr:
        parsed = parse_qr_data(raw_qr)
        if not parsed:
            raise ValueError("❌ Format QR invalide.")
        return parsed["matricule"], parsed["token"]

    if matricule:
        try:
            employe = Employe.objects.get(matricule=matricule, actif=True)
        except Employe.DoesNotExist:
            raise ValueError(f"❌ Employé {matricule} non trouvé.")
        return employe.matricule, str(employe.qr_code_token)

    raise ValueError("❌ QR code ou matricule requis.")


def _resolve_site(site_id):
    if not site_id:
        raise ValueError("❌ Veuillez sélectionner un site.")
    try:
        site_id = int(site_id)
    except (TypeError, ValueError):
        raise ValueError("❌ Site invalide.")
    try:
        return Site.objects.get(pk=site_id)
    except Site.DoesNotExist:
        raise ValueError("❌ Site invalide.")


def _detecter_sortie_anticipee(employe, site, now):
    """Prévisualise la décision sans écrire en base."""
    context = collect_day_context(
        employee_id=employe.id,
        site=site,
        date_target=now.date(),
        current_time=now.time(),
        lock=False,
    )
    decision = DayStateMachine().decide(context)

    if not decision.allowed or decision.action not in {
        ScanActionType.MORNING_EXIT,
        ScanActionType.AFTERNOON_EXIT,
    }:
        return None

    periode = decision.period.value
    _, heure_fermeture = site.get_horaires_pour_periode(periode)
    if not heure_fermeture:
        return None

    fermeture_dt = datetime.combine(now.date(), heure_fermeture)
    depart_dt = datetime.combine(now.date(), now.time())
    avance = fermeture_dt - depart_dt
    seuil = site.seuil_depart_anticipe_minutes
    if seuil is None:
        seuil = 15

    if avance.total_seconds() < seuil * 60:
        return None

    return {
        "periode": periode,
        "heure_depart": now.strftime("%H:%M"),
        "heure_fermeture": heure_fermeture.strftime("%H:%M"),
        "minutes_avance": int(avance.total_seconds() // 60),
    }


@login_required
def scanner_web_view(request):
    """Scanner Web compatible avec l'ancien flux, avec confirmation anticipée."""
    if request.method == "GET":
        return views.scanner_view(request)

    if request.POST.get("action") == "confirmer_sortie_anticipee":
        return confirmer_sortie_anticipee(request)

    raw_qr = request.POST.get("qr_data", "").strip()
    matricule = request.POST.get("matricule", "").strip()
    site_id = request.POST.get("site_id")
    periode_type = request.POST.get("periode_type", "auto")

    try:
        mat, token = _resolve_scan_identity(raw_qr, matricule)
        site = _resolve_site(site_id)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("scanner")

    if periode_type != "garde":
        employe = Employe.objects.get(matricule=mat, actif=True)
        now = timezone.localtime(timezone.now())
        anticipation = _detecter_sortie_anticipee(employe, site, now)
        if anticipation:
            request.session[PENDING_SESSION_KEY] = {
                "matricule": mat,
                "qr_token": token,
                "site_id": site.id,
                "mode": "auto",
                "created_at": now.isoformat(),
                "captured_at": now.isoformat(),
                "client_event_id": str(uuid.uuid4()),
                **anticipation,
            }
            request.session.modified = True
            return render(request, "pointage/sortie_anticipee_confirmation.html", {
                "employe": employe,
                "site": site,
                "anticipation": anticipation,
            })

    # Aucun départ anticipé : comportement historique inchangé.
    return views.scanner_view(request)


@login_required
def confirmer_sortie_anticipee(request):
    if request.method != "POST":
        return redirect("scanner")

    pending = request.session.get(PENDING_SESSION_KEY)
    if not pending:
        messages.error(request, "❌ Cette confirmation de sortie a expiré. Veuillez rescanner.")
        return redirect("scanner")

    motif = request.POST.get("motif", "").strip()
    if len(motif) < 3:
        messages.error(request, "❌ Le motif de la sortie anticipée est obligatoire.")
        return redirect("scanner")

    try:
        employe = Employe.objects.get(matricule=pending["matricule"], actif=True)
        site = Site.objects.get(pk=pending["site_id"])
        captured_at = datetime.fromisoformat(pending["captured_at"])
        client_event_id = pending["client_event_id"]
        uuid.UUID(client_event_id)
    except (Employe.DoesNotExist, Site.DoesNotExist, KeyError, TypeError, ValueError):
        request.session.pop(PENDING_SESSION_KEY, None)
        messages.error(request, "❌ Les informations du scan ne sont plus valides.")
        return redirect("scanner")

    result = process_scan(
        matricule=employe.matricule,
        qr_token=pending["qr_token"],
        site_id=site.id,
        mode=pending.get("mode", "auto"),
        client_event_id=client_event_id,
        captured_at=captured_at,
    )

    request.session.pop(PENDING_SESSION_KEY, None)

    if result.get("status") != "success":
        if result.get("status") == "warning":
            messages.warning(request, f"⚠️ {result.get('message')}")
        else:
            messages.error(request, f"❌ {result.get('message')}")
        return redirect("scanner")

    pointage_id = (result.get("data") or {}).get("pointage_id")
    anomalie = None
    if pointage_id:
        anomalies = AnomaliePointage.objects.filter(
            employe=employe,
            date_pointage=captured_at.date(),
            type=AnomaliePointage.TYPE_DEPART_ANTICIPE,
            statut=AnomaliePointage.STATUT_OUVERTE,
        ).order_by("-created_at")
        for candidate in anomalies:
            if (candidate.contexte or {}).get("pointage_id") == pointage_id:
                anomalie = candidate
                break

    if anomalie:
        contexte = dict(anomalie.contexte or {})
        contexte.update({
            "motif_employe": motif,
            "autorisation_rh": "en_attente",
            "demande_autorisation": True,
        })
        anomalie.contexte = contexte
        anomalie.save(update_fields=["contexte"])

    messages.success(
        request,
        f"✅ Sortie enregistrée à {(result.get('data') or {}).get('heure_depart', pending.get('heure_depart', ''))}. "
        "Votre motif a été transmis pour validation RH."
    )
    return redirect("scanner")
