"""Garde-fous transversaux de l'administration RH.

Ce module complète les ModelAdmin existants sans dupliquer leur présentation.
Il verrouille les traces de pointage/audit et empêche qu'un compte staff créé
hors du workflow normal puisse contourner le rôle RH.
"""

from django.contrib import admin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import (
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


def _pointage_readonly_fields(self, request, obj=None):
    """Un pointage est une trace : aucune modification directe dans l'admin.

    Les corrections passent par le workflow d'anomalie/demande, qui conserve
    l'auteur, les anciennes valeurs et les nouvelles valeurs dans l'audit.
    """
    return tuple(field.name for field in self.model._meta.concrete_fields)


def _pointage_actions(self, request):
    """Retire les anciennes actions qui falsifiaient directement le statut."""
    return [
        action
        for action in (getattr(self, "actions", []) or [])
        if action not in {"marquer_present", "marquer_retard", "marquer_absent", "supprimer_selection"}
    ]


def _no_delete(self, request, obj=None):
    return False


def _custom_user_fieldsets(self, request, obj=None):
    """Expose uniquement les attributs qu'un RH peut administrer.

    En particulier, is_superuser/groups/user_permissions ne doivent jamais
    être attribuables depuis l'interface à un simple administrateur RH.
    """
    return (
        ("Connexion", {"fields": ("username", "password")}),
        ("Identité", {"fields": ("first_name", "last_name", "email")}),
        ("Rôle & accès", {"fields": ("role", "is_active", "is_staff")} ),
    )


def _custom_user_add_fieldsets(self, request, obj=None):
    return (
        (None, {"classes": ("wide",), "fields": ("username", "password1", "password2")} ),
        ("Identité", {"fields": ("first_name", "last_name", "email")} ),
        ("Rôle & accès", {"fields": ("role", "is_active")} ),
    )


def _custom_user_readonly_fields(self, request, obj=None):
    return ("is_staff",)


def _safe_request_action(self, request, pk, approve):
    """Les actions d'une demande ne modifient jamais l'état sur GET.

    GET affiche une page de confirmation ; POST + CSRF réalise l'opération.
    Cela évite qu'un simple lien, préchargement ou crawler puisse approuver
    ou refuser une demande RH.
    """
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

    # Les ModelAdmin doivent être enregistrés avant ce module. L'import explicite
    # garantit ce contrat lorsque AppConfig.ready() est appelé tôt au démarrage.
    if Pointage not in registry:
        from . import admin as _pointage_admin  # noqa: F401
        registry = admin.site._registry

    # Toutes les interfaces RH sont accessibles uniquement à un compte RH réel.
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

    pointage_admin = registry.get(Pointage)
    if pointage_admin:
        cls = pointage_admin.__class__
        cls.get_readonly_fields = _pointage_readonly_fields
        cls.get_actions = _pointage_actions
        cls.has_delete_permission = _no_delete

    # Les événements bruts et les audits sont immuables et non supprimables.
    for model in (Scan, AnomaliePointage, AnomalieTraitement, PointageAudit):
        model_admin = registry.get(model)
        if model_admin:
            model_admin.__class__.has_delete_permission = _no_delete

    # Les demandes restent dans l'historique : pas de suppression.
    demande_admin = registry.get(DemandeModification)
    if demande_admin:
        cls = demande_admin.__class__
        cls.has_delete_permission = _no_delete
        cls.approuver_view = _safe_approve
        cls.refuser_view = _safe_refuse

    # Empêche un administrateur RH de s'accorder les privilèges Django de
    # superutilisateur ou de modifier les groupes/permissions système.
    user_admin = registry.get(__import__("pointage.models", fromlist=["CustomUser"]).CustomUser)
    if user_admin:
        cls = user_admin.__class__
        cls.has_module_permission = _rh_module_permission
        cls.has_view_permission = _rh_view_permission
        cls.has_add_permission = _rh_add_permission
        cls.has_change_permission = _rh_change_permission
        cls.has_delete_permission = _rh_delete_permission
        cls.get_fieldsets = _custom_user_fieldsets
        cls.add_fieldsets = _custom_user_add_fieldsets(None, None) if False else cls.add_fieldsets
        cls.get_readonly_fields = _custom_user_readonly_fields

        def get_add_fieldsets(self, request):
            return _custom_user_add_fieldsets(self, request)

        cls.get_add_fieldsets = get_add_fieldsets

        original_save_model = getattr(cls, "save_model", None)
        def save_model(self, request, obj, form, change):
            if not _is_rh(request.user):
                return
            obj.is_superuser = False
            obj.is_staff = True
            if getattr(obj, "role", None) != "admin":
                obj.is_staff = False
            if original_save_model:
                original_save_model(self, request, obj, form, change)
            else:
                super(cls, self).save_model(request, obj, form, change)
        cls.save_model = save_model


install()
