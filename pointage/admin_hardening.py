"""Garde-fous transversaux de l'administration RH."""

from django.contrib import admin
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import (
    CustomUser,
    Pointage,
    Scan,
    DemandeModification,
    AnomaliePointage,
    AnomalieTraitement,
    PointageAudit,
)


def _is_rh(user):
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or getattr(user, "role", None) == "admin")
    )


def _rh_module_permission(self, request):
    return _is_rh(request.user)


def _rh_view_permission(self, request, obj=None):
    return _is_rh(request.user)


def _rh_add_permission(self, request):
    return _is_rh(request.user)


def _rh_change_permission(self, request, obj=None):
    return _is_rh(request.user)


def _rh_delete_permission(self, request, obj=None):
    return _is_rh(request.user)


def _immutable_readonly_fields(self, request, obj=None):
    """Conserve les champs readonly existants et verrouille tous les champs DB."""
    existing = getattr(self, "readonly_fields", ()) or ()
    concrete = tuple(field.name for field in self.model._meta.concrete_fields)
    return tuple(dict.fromkeys((*existing, *concrete)))


def _no_add(self, request):
    return False


def _no_delete(self, request, obj=None):
    return False


def _remove_unsafe_pointage_actions(self):
    """Retire les actions qui pouvaient falsifier directement un pointage."""
    self.actions = [
        action
        for action in (getattr(self, "actions", []) or [])
        if action not in {
            "marquer_present",
            "marquer_retard",
            "marquer_absent",
            "supprimer_selection",
        }
    ]


def _custom_user_fieldsets(self, request, obj=None):
    """Un RH ne peut pas attribuer superuser, groupes ou permissions système."""
    return (
        ("Connexion", {"fields": ("username", "password")}),
        ("Identité", {"fields": ("first_name", "last_name", "email")}),
        ("Rôle & accès", {"fields": ("role", "is_active", "is_staff")}),
    )


def _custom_user_add_fieldsets(self, request):
    return (
        (None, {"classes": ("wide",), "fields": ("username", "password1", "password2")}),
        ("Identité", {"fields": ("first_name", "last_name", "email")}),
        ("Rôle & accès", {"fields": ("role", "is_active")}),
    )


def _custom_user_readonly_fields(self, request, obj=None):
    return ("is_staff",)


@transaction.atomic
def _safe_request_action(self, request, pk, approve):
    """GET affiche une confirmation ; seul POST + CSRF change l'état."""
    demande = get_object_or_404(DemandeModification, pk=pk)

    if not _is_rh(request.user):
        self.message_user(request, "Permission refusée : validation RH requise.", level=messages.ERROR)
        return redirect("admin:index")

    action = "approuver" if approve else "refuser"
    if demande.statut != "en_attente":
        self.message_user(request, f"La demande #{pk} est déjà traitée.", level=messages.WARNING)
        return redirect("../../")

    if request.method == "GET":
        return render(request, "admin/pointage/demande/confirm_action.html", {
            "title": f"Confirmer : {action} la demande #{pk}",
            "demande": demande,
            "action": action,
            "opts": self.model._meta,
            "cancel_url": "../../",
        })

    if request.method != "POST":
        self.message_user(request, "Méthode HTTP non autorisée.", level=messages.ERROR)
        return redirect("../../")

    try:
        if approve:
            self._appliquer_demande(demande)
            demande.statut = "approuvee"
        else:
            demande.statut = "refusee"
        demande.traitee_par = request.user
        demande.date_traitement = timezone.now()
        demande.save(update_fields=("statut", "traitee_par", "date_traitement"))
        self.message_user(
            request,
            f"Demande #{pk} {'approuvée et appliquée' if approve else 'refusée'}.",
            level=messages.SUCCESS,
        )
    except Exception:
        transaction.set_rollback(True)
        self.message_user(
            request,
            "Le traitement a échoué. Aucune modification n'a été enregistrée.",
            level=messages.ERROR,
        )

    return redirect("../../")


def _safe_approve(self, request, pk):
    return _safe_request_action(self, request, pk, True)


def _safe_refuse(self, request, pk):
    return _safe_request_action(self, request, pk, False)


def install():
    registry = admin.site._registry

    # AppConfig.ready() peut s'exécuter avant autodiscover : charger le module
    # admin garantit que les ModelAdmin de cette application existent.
    if Pointage not in registry:
        from . import admin as _pointage_admin  # noqa: F401
        registry = admin.site._registry

    protected_models = (
        Pointage,
        Scan,
        DemandeModification,
        AnomaliePointage,
        AnomalieTraitement,
        PointageAudit,
    )
    for model in protected_models:
        model_admin = registry.get(model)
        if not model_admin:
            continue
        cls = model_admin.__class__
        cls.has_module_permission = _rh_module_permission
        cls.has_view_permission = _rh_view_permission
        cls.has_add_permission = _rh_add_permission
        cls.has_change_permission = _rh_change_permission
        cls.has_delete_permission = _rh_delete_permission

    # Pointage, scans, traitements et audits sont des traces immuables.
    for model in (Pointage, Scan, AnomalieTraitement, PointageAudit):
        model_admin = registry.get(model)
        if not model_admin:
            continue
        cls = model_admin.__class__
        cls.get_readonly_fields = _immutable_readonly_fields
        cls.has_add_permission = _no_add
        cls.has_delete_permission = _no_delete

    pointage_admin = registry.get(Pointage)
    if pointage_admin:
        _remove_unsafe_pointage_actions(pointage_admin)

    # Une anomalie ne doit être créée/modifiée/supprimée que par ses workflows.
    anomalie_admin = registry.get(AnomaliePointage)
    if anomalie_admin:
        cls = anomalie_admin.__class__
        cls.has_add_permission = _no_add
        cls.has_delete_permission = _no_delete
        cls.get_readonly_fields = _immutable_readonly_fields

    # Les demandes restent dans l'historique et leurs actions mutantes sont
    # désormais POST + CSRF via une page de confirmation.
    demande_admin = registry.get(DemandeModification)
    if demande_admin:
        cls = demande_admin.__class__
        cls.has_add_permission = _no_add
        cls.has_delete_permission = _no_delete
        cls.approuver_view = _safe_approve
        cls.refuser_view = _safe_refuse

    # Un administrateur RH ne peut pas devenir superutilisateur ni administrer
    # les groupes/permissions Django.
    user_admin = registry.get(CustomUser)
    if user_admin:
        cls = user_admin.__class__
        cls.has_module_permission = _rh_module_permission
        cls.has_view_permission = _rh_view_permission
        cls.has_add_permission = _rh_add_permission
        cls.has_change_permission = _rh_change_permission
        cls.has_delete_permission = _rh_delete_permission
        cls.get_fieldsets = _custom_user_fieldsets
        cls.get_add_fieldsets = _custom_user_add_fieldsets
        cls.get_readonly_fields = _custom_user_readonly_fields

        original_save_model = getattr(cls, "save_model", None)

        def save_model(self, request, obj, form, change):
            if not _is_rh(request.user):
                return
            obj.is_superuser = False
            obj.is_staff = getattr(obj, "role", None) == "admin"
            if original_save_model:
                original_save_model(self, request, obj, form, change)

        cls.save_model = save_model


install()
