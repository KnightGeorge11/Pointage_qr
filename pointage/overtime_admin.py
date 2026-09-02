from django.contrib import admin, messages
from django.utils import timezone

from .models import Pointage


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


def autoriser_heures_supplementaires(modeladmin, request, queryset):
    if not request.user.is_staff:
        modeladmin.message_user(request, "Permission refusée.", level=messages.ERROR)
        return

    count = 0
    for pointage in queryset.select_related('site', 'employe'):
        if not pointage.heures_supplementaires or pointage.heures_supplementaires.total_seconds() <= 0:
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


def refuser_heures_supplementaires(modeladmin, request, queryset):
    if not request.user.is_staff:
        modeladmin.message_user(request, "Permission refusée.", level=messages.ERROR)
        return

    count = 0
    for pointage in queryset:
        before = {
            'heures_supplementaires': str(pointage.heures_supplementaires or 0),
            'heures_supplementaires_autorisees': pointage.heures_supplementaires_autorisees,
            'autorisees_par': pointage.heures_supplementaires_autorisees_par_id,
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
    if obj.heures_supplementaires_autorisees:
        return f"✅ {minutes // 60}h{minutes % 60:02d}"
    return f"⏳ {minutes // 60}h{minutes % 60:02d} (non autorisées)"

_heures_sup_autorisees_display.short_description = "H. supp."


def install():
    pointage_admin = _get_pointage_admin()
    if pointage_admin is None:
        return

    cls = pointage_admin.__class__
    if getattr(cls, '_overtime_hardening_installed', False):
        return

    setattr(cls, 'heures_sup_autorisees_display', _heures_sup_autorisees_display)

    actions = list(getattr(pointage_admin, 'actions', []) or [])
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
