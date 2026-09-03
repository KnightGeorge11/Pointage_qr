from django.contrib import admin, messages
from django.utils import timezone
from django.db import transaction
from django.utils.html import format_html

from .models import Pointage


def _has_rh_permission(user):
    """Les actions RH sensibles sont réservées aux administrateurs/superusers."""
    return bool(user and user.is_authenticated and (user.is_superuser or user.role == 'admin'))


def _get_pointage_admin():
    return admin.site._registry.get(Pointage)


def _audit_overtime_change(pointage, user, before, after, motif):
    from .models import PointageAudit
    PointageAudit.objects.create(
        pointage=pointage,
        administrateur=user,
        action=PointageAudit.ACTION_UPDATE,
        avant=before,
        apres=after,
        motif=motif,
    )


@transaction.atomic
def autoriser_heures_supplementaires(modeladmin, request, queryset):
    if not _has_rh_permission(request.user):
        modeladmin.message_user(request, "Permission refusée : validation RH requise.", level=messages.ERROR)
        return

    count = 0
    for pointage in queryset.select_for_update().select_related('site', 'employe'):
        # Le trigger PostgreSQL remet à zéro le champ tant que l'autorisation
        # est False. Il faut donc recalculer depuis les heures d'arrivée/départ
        # avant de décider si le pointage contient réellement des H.Supp.
        pointage.calculer_heures_supplementaires()
        if not pointage.heures_supplementaires or pointage.heures_supplementaires.total_seconds() <= 0:
            continue
        if pointage.heures_supplementaires_autorisees:
            continue

        before = {
            'heures_supplementaires': str(pointage.heures_supplementaires),
            'heures_supplementaires_autorisees': pointage.heures_supplementaires_autorisees,
            'autorisees_par': pointage.heures_supplementaires_autorisees_par_id,
            'date_autorisation': (
                pointage.date_autorisation_heures_supplementaires.isoformat()
                if pointage.date_autorisation_heures_supplementaires else None
            ),
        }

        pointage.heures_supplementaires_autorisees = True
        pointage.heures_supplementaires_autorisees_par = request.user
        pointage.date_autorisation_heures_supplementaires = timezone.now()
        pointage.motif_autorisation_heures_supplementaires = "Validation RH depuis l'administration."
        pointage.save()

        after = {
            'heures_supplementaires': str(pointage.heures_supplementaires or 0),
            'heures_supplementaires_autorisees': True,
            'autorisees_par': request.user_id,
            'date_autorisation': pointage.date_autorisation_heures_supplementaires.isoformat(),
        }
        _audit_overtime_change(
            pointage, request.user, before, after,
            pointage.motif_autorisation_heures_supplementaires,
        )
        count += 1

    modeladmin.message_user(
        request,
        f"{count} pointage(s) avec heures supplémentaires autorisé(s).",
        level=messages.SUCCESS,
    )


autoriser_heures_supplementaires.short_description = "✅ Autoriser les heures supplémentaires"


@transaction.atomic
def refuser_heures_supplementaires(modeladmin, request, queryset):
    if not _has_rh_permission(request.user):
        modeladmin.message_user(request, "Permission refusée : validation RH requise.", level=messages.ERROR)
        return

    count = 0
    for pointage in queryset.select_for_update():
        before = {
            'heures_supplementaires': str(pointage.heures_supplementaires or 0),
            'heures_supplementaires_autorisees': pointage.heures_supplementaires_autorisees,
            'autorisees_par': pointage.heures_supplementaires_autorisees_par_id,
            'date_autorisation': (
                pointage.date_autorisation_heures_supplementaires.isoformat()
                if pointage.date_autorisation_heures_supplementaires else None
            ),
        }

        pointage.heures_supplementaires_autorisees = False
        pointage.heures_supplementaires_autorisees_par = None
        pointage.date_autorisation_heures_supplementaires = None
        pointage.motif_autorisation_heures_supplementaires = "Autorisation révoquée par la RH."
        pointage.save()

        after = {
            'heures_supplementaires': str(pointage.heures_supplementaires or 0),
            'heures_supplementaires_autorisees': False,
            'autorisees_par': None,
            'date_autorisation': None,
        }
        _audit_overtime_change(
            pointage, request.user, before, after,
            pointage.motif_autorisation_heures_supplementaires,
        )
        count += 1

    modeladmin.message_user(
        request,
        f"{count} pointage(s) : heures supplémentaires révoquées.",
        level=messages.SUCCESS,
    )


refuser_heures_supplementaires.short_description = "🚫 Révoquer les heures supplémentaires"


def _heures_sup_autorisees_display(self, obj):
    if not obj.heures_supplementaires or obj.heures_supplementaires.total_seconds() <= 0:
        return "—"

    minutes = int(obj.heures_supplementaires.total_seconds() // 60)
    label = f"{minutes // 60}h{minutes % 60:02d}"

    if obj.heures_supplementaires_autorisees:
        return format_html(
            '<span style="background:#F0FDF4;color:#15803D;padding:3px 9px;'
            'border-radius:9999px;font-weight:600;font-size:11px;">✓ {} validées</span>',
            label,
        )

    return format_html(
        '<span style="background:#FFFBEB;color:#D97706;padding:3px 9px;'
        'border-radius:9999px;font-weight:600;font-size:11px;">⏳ {} à valider</span>',
        label,
    )


_heures_sup_autorisees_display.short_description = "H. supp."


def _has_delete_permission(self, request, obj=None):
    """Un pointage est une trace de présence : pas de suppression depuis l'admin.

    Les corrections doivent passer par le workflow de modification/anomalie,
    afin de conserver la traçabilité dans PointageAudit.
    """
    return False


def install():
    pointage_admin = _get_pointage_admin()
    if pointage_admin is None:
        return

    cls = pointage_admin.__class__
    if getattr(cls, '_overtime_hardening_installed', False):
        return

    setattr(cls, 'heures_sup_autorisees_display', _heures_sup_autorisees_display)
    setattr(cls, 'has_delete_permission', _has_delete_permission)

    actions = list(getattr(pointage_admin, 'actions', []) or [])
    actions = [a for a in actions if a != 'supprimer_selection']
    for action_name in ('autoriser_heures_supplementaires', 'refuser_heures_supplementaires'):
        if action_name not in actions:
            actions.append(action_name)
    pointage_admin.actions = actions

    current_display = list(getattr(pointage_admin, 'list_display', []) or [])
    if 'heures_sup_autorisees_display' not in current_display:
        current_display.append('heures_sup_autorisees_display')
    pointage_admin.list_display = current_display

    setattr(cls, 'autoriser_heures_supplementaires', autoriser_heures_supplementaires)
    setattr(cls, 'refuser_heures_supplementaires', refuser_heures_supplementaires)
    cls._overtime_hardening_installed = True


install()
