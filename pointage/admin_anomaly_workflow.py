"""Actions unitaires des anomalies depuis l'espace d'administration."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.db import transaction

from .admin_security import _is_rh
from .anomalies import marquer_cloturee, marquer_traitee
from .models import AnomaliePointage, AnomalieTraitement


@login_required
def admin_anomaly_workflow(request, pk):
    """Panneau de traitement RH accessible depuis Jazzmin."""
    if not _is_rh(request.user):
        return HttpResponseForbidden("Accès réservé au personnel RH.")

    if request.method == "POST":
        try:
            with transaction.atomic():
                # Verrouiller uniquement la ligne d'anomalie. Les relations
                # employé/site sont nullable et PostgreSQL interdit FOR UPDATE
                # sur leur côté nullable lorsqu'elles sont jointes en LEFT JOIN.
                anomalie = get_object_or_404(
                    AnomaliePointage.objects.select_for_update(),
                    pk=pk,
                )
                action = (request.POST.get("action") or "").strip().lower()
                commentaire = (request.POST.get("commentaire") or "").strip()

                if anomalie.statut == AnomaliePointage.STATUT_CLOTUREE:
                    raise ValueError("Cette anomalie est déjà clôturée et ne peut plus être modifiée.")

                if action in {"justification", "rejet"}:
                    if not commentaire:
                        raise ValueError("Le commentaire est obligatoire pour cette action.")
                    marquer_traitee(
                        anomalie,
                        request.user,
                        type_action=(
                            AnomalieTraitement.ACTION_JUSTIFICATION
                            if action == "justification"
                            else AnomalieTraitement.ACTION_REJET
                        ),
                        commentaire=commentaire,
                        corrections=[],
                    )
                    messages.success(
                        request,
                        f"Anomalie #{anomalie.pk} : {'justification enregistrée' if action == 'justification' else 'rejet enregistré'}. Elle est maintenant traitée.",
                    )

                elif action == "cloture":
                    if anomalie.statut != AnomaliePointage.STATUT_TRAITEE:
                        raise ValueError("Une anomalie doit être traitée avant de pouvoir être clôturée.")
                    marquer_cloturee(anomalie, request.user)
                    messages.success(request, f"Anomalie #{anomalie.pk} clôturée avec succès.")

                elif action == "corriger":
                    return redirect(reverse("admin:anomalie_corriger_pointage", args=[anomalie.pk]))

                else:
                    raise ValueError("Action d'anomalie inconnue.")

        except (ValueError, PermissionError) as exc:
            messages.error(request, str(exc))

        return redirect(reverse("admin_anomaly_workflow", args=[pk]))

    anomalie = get_object_or_404(
        AnomaliePointage.objects.select_related("employe", "site"),
        pk=pk,
    )
    return render(request, "admin/pointage/anomalie/admin_anomaly_workflow.html", {
        "anomalie": anomalie,
        "opts": AnomaliePointage._meta,
        "site_header": "Pointage QR — Administration",
        "site_title": "Pointage QR",
        "has_permission": True,
    })
