from django.contrib import admin
from django.utils.safestring import mark_safe
from django.urls import path
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from .models import (
    Employe, Site, Pointage, Scan, Poste,
    CustomUser, DemandeModification, AlerteRH, AutorisationSortie
)
import uuid


# ============================================================
# CUSTOM USER
# ============================================================

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display  = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff')
    list_filter   = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering      = ('username',)

    fieldsets = UserAdmin.fieldsets + (
        ('Rôle & Permissions', {'fields': ('role',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Rôle & Permissions', {'fields': ('role',)}),
    )

    def save_model(self, request, obj, form, change):
        if obj.role == 'admin':
            obj.is_staff = True
        else:
            obj.is_staff    = False
            obj.is_superuser = False
        super().save_model(request, obj, form, change)


# ============================================================
# DEMANDE DE MODIFICATION
# ============================================================

@admin.register(DemandeModification)
class DemandeModificationAdmin(admin.ModelAdmin):
    list_display  = ('demandeur', 'type_action', 'cible', 'statut_badge', 'date_creation', 'boutons_action')
    list_filter   = ('statut', 'type_action', 'cible')
    search_fields = ('demandeur__username',)
    actions       = ['approuver_demandes', 'refuser_demandes']

    # Tout en readonly sauf commentaire
    readonly_fields = (
        'demandeur', 'type_action', 'cible',
        'donnees_formatees', 'statut_badge',
        'date_creation', 'traitee_par', 'date_traitement',
        'boutons_fiche',
    )

    fieldsets = (
        ('Informations', {
            'fields': ('demandeur', 'type_action', 'cible','date_creation')
        }),
        ('Données soumises', {
            'fields': ('donnees_formatees',)
        }),
        ('Statut', {
            'fields': ('statut_badge', 'traitee_par', 'date_traitement')
        }),
        ('Commentaire', {
            'fields': ('commentaire',)
        }),
    )

    def has_add_permission(self, request):
        return False

    # ── Badge statut ────────────────────────────────────────────

    def statut_badge(self, obj):
        styles = {
            'en_attente': ('rgba(251,191,36,.12)',  '#fbbf24', '⏳ En attente'),
            'approuvee':  ('rgba(74,222,128,.12)',   '#4ade80', '✅ Approuvée'),
            'refusee':    ('rgba(248,113,113,.12)',  '#f87171', '❌ Refusée'),
        }
        bg, color, label = styles.get(obj.statut, ('rgba(255,255,255,.07)', '#e8eaf0', obj.statut))
        return mark_safe(
            f'<span style="background:{bg};color:{color};padding:4px 12px;'
            f'border-radius:20px;font-size:12px;font-weight:600;white-space:nowrap;">'
            f'{label}</span>'
        )
    statut_badge.short_description = 'Statut'

    # ── Boutons dans le tableau (liste) ─────────────────────────

    def boutons_action(self, obj):
        from django.urls import reverse
        if obj.statut != 'en_attente':
            return mark_safe(
                '<span style="color:rgba(232,234,240,.3);font-size:12px;font-style:italic;">Traitée</span>'
            )
        url_approuver = reverse('admin:demande_approuver', args=[obj.pk])
        url_refuser   = reverse('admin:demande_refuser',   args=[obj.pk])
        return mark_safe(
            f'<div style="display:flex;gap:6px;">'
            f'<a href="{url_approuver}" style="background:rgba(74,222,128,.12);color:#4ade80;'
            f'border:1px solid rgba(74,222,128,.3);padding:4px 12px;border-radius:6px;'
            f'font-size:11px;font-weight:600;text-decoration:none;white-space:nowrap;">✅ Accepter</a>'
            f'<a href="{url_refuser}" style="background:rgba(248,113,113,.12);color:#f87171;'
            f'border:1px solid rgba(248,113,113,.3);padding:4px 12px;border-radius:6px;'
            f'font-size:11px;font-weight:600;text-decoration:none;white-space:nowrap;">❌ Refuser</a>'
            f'</div>'
        )
    boutons_action.short_description = 'Actions'

    # ── Boutons dans la fiche (détail) ──────────────────────────

    def boutons_fiche(self, obj):
        btn_retour = (
            '<a href="../" style="display:inline-flex;align-items:center;gap:6px;'
            'background:rgba(255,255,255,.06);color:#e8eaf0;'
            'border:1px solid rgba(255,255,255,.15);padding:8px 18px;'
            'border-radius:6px;font-size:13px;font-weight:600;text-decoration:none;">'
            '← Retour</a>'
        )
        if obj.statut != 'en_attente':
            return mark_safe(btn_retour)

        return mark_safe(
            '<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">'
            '<button type="submit" name="_accepter" value="1" '
            'style="background:rgba(74,222,128,.15);color:#4ade80;'
            'border:1px solid rgba(74,222,128,.35);padding:8px 20px;'
            'border-radius:6px;font-size:13px;font-weight:600;cursor:pointer;">'
            '✅ Accepter</button>'
            '<button type="submit" name="_refuser" value="1" '
            'style="background:rgba(248,113,113,.15);color:#f87171;'
            'border:1px solid rgba(248,113,113,.35);padding:8px 20px;'
            'border-radius:6px;font-size:13px;font-weight:600;cursor:pointer;">'
            '❌ Refuser</button>'
            + btn_retour +
            '</div>'
        )
    boutons_fiche.short_description = ''

    # ── URLs personnalisées ─────────────────────────────────────

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('<int:pk>/approuver/', self.admin_site.admin_view(self.approuver_view), name='demande_approuver'),
            path('<int:pk>/refuser/',   self.admin_site.admin_view(self.refuser_view),   name='demande_refuser'),
        ]
        return custom + urls

    def approuver_view(self, request, pk):
        from django.shortcuts import get_object_or_404
        demande = get_object_or_404(DemandeModification, pk=pk)
        if demande.statut == 'en_attente':
            try:
                self._appliquer_demande(demande)
                demande.statut          = 'approuvee'
                demande.traitee_par     = request.user
                demande.date_traitement = timezone.now()
                demande.save()
                self.message_user(request, f"✅ Demande #{pk} approuvée et appliquée.")
            except Exception as e:
                self.message_user(request, f"❌ Erreur : {e}", level='error')
        return HttpResponseRedirect("../../")

    def refuser_view(self, request, pk):
        from django.shortcuts import get_object_or_404
        demande = get_object_or_404(DemandeModification, pk=pk)
        if demande.statut == 'en_attente':
            demande.statut          = 'refusee'
            demande.traitee_par     = request.user
            demande.date_traitement = timezone.now()
            demande.save()
            self.message_user(request, f"❌ Demande #{pk} refusée.")
        return HttpResponseRedirect("../../")

    # ── Intercept boutons dans la fiche ────────────────────────

    def response_change(self, request, obj):
        if '_accepter' in request.POST and obj.statut == 'en_attente':
            try:
                self._appliquer_demande(obj)
                obj.statut          = 'approuvee'
                obj.traitee_par     = request.user
                obj.date_traitement = timezone.now()
                obj.save()
                self.message_user(request, f"✅ Demande #{obj.pk} approuvée et appliquée.")
            except Exception as e:
                self.message_user(request, f"❌ Erreur : {e}", level='error')
            return HttpResponseRedirect("../")

        if '_refuser' in request.POST and obj.statut == 'en_attente':
            obj.statut          = 'refusee'
            obj.traitee_par     = request.user
            obj.date_traitement = timezone.now()
            obj.save()
            self.message_user(request, f"❌ Demande #{obj.pk} refusée.")
            return HttpResponseRedirect("../")

        return super().response_change(request, obj)

    # ── save_model — protège tout sauf commentaire ──────────────

    def save_model(self, request, obj, form, change):
        if change:
            original            = DemandeModification.objects.get(pk=obj.pk)
            obj.demandeur       = original.demandeur
            obj.type_action     = original.type_action
            obj.cible           = original.cible
            obj.cible_id        = original.cible_id
            obj.donnees         = original.donnees
            obj.statut          = original.statut
            obj.traitee_par     = original.traitee_par
            obj.date_traitement = original.date_traitement
        super().save_model(request, obj, form, change)

    # ── Données formatées ───────────────────────────────────────

    def donnees_formatees(self, obj):
        if not obj.donnees:
            return '—'
        lignes = []
        for cle, valeur in obj.donnees.items():
            lignes.append(
                f'<tr>'
                f'<td style="padding:8px 14px;color:rgba(255,255,255,.45);font-size:11px;'
                f'text-transform:uppercase;letter-spacing:.08em;white-space:nowrap;'
                f'border-bottom:1px solid rgba(255,255,255,.06)">{cle}</td>'
                f'<td style="padding:8px 14px;font-weight:500;color:#e8eaf0;'
                f'border-bottom:1px solid rgba(255,255,255,.06)">{valeur}</td>'
                f'</tr>'
            )
        return mark_safe(
            '<table style="border-collapse:collapse;width:100%;background:#1c2236;'
            'border-radius:8px;overflow:hidden;border:1px solid rgba(255,255,255,.07)">'
            + ''.join(lignes)
            + '</table>'
        )
    donnees_formatees.short_description = "Données de la demande"

    # ── Actions groupées ────────────────────────────────────────

    @admin.action(description="✅ Approuver les demandes sélectionnées")
    def approuver_demandes(self, request, queryset):
        for demande in queryset.filter(statut='en_attente'):
            try:
                self._appliquer_demande(demande)
                demande.statut          = 'approuvee'
                demande.traitee_par     = request.user
                demande.date_traitement = timezone.now()
                demande.save()
            except Exception as e:
                self.message_user(request, f"❌ Erreur demande #{demande.pk} : {e}", level='error')
        self.message_user(request, "✅ Demandes approuvées et appliquées.")

    @admin.action(description="❌ Refuser les demandes sélectionnées")
    def refuser_demandes(self, request, queryset):
        for demande in queryset.filter(statut='en_attente'):
            demande.statut          = 'refusee'
            demande.traitee_par     = request.user
            demande.date_traitement = timezone.now()
            demande.save()
        self.message_user(request, "❌ Demandes refusées.")

    # ── Application en base ─────────────────────────────────────

    def _appliquer_demande(self, demande):
        d = demande.donnees

        if demande.cible == 'employe':
            if demande.type_action == 'create':
                Employe.objects.create(
                    nom=d['nom'], prenom=d['prenom'],
                    matricule=d['matricule'],
                    poste_id=d.get('poste'),
                    actif=d.get('actif', True)
                )
            elif demande.type_action == 'update':
                Employe.objects.filter(pk=demande.cible_id).update(
                    nom=d['nom'], prenom=d['prenom'],
                    matricule=d['matricule'],
                    poste_id=d.get('poste'),
                    actif=d.get('actif', True)
                )
            elif demande.type_action == 'delete':
                Employe.objects.filter(pk=demande.cible_id).update(actif=False)

        elif demande.cible == 'site':
            if demande.type_action == 'create':
                Site.objects.create(
                    nom=d['nom'], adresse=d.get('adresse', ''),
                    heure_ouverture_matin=d['heure_ouverture_matin'],
                    heure_fermeture_matin=d['heure_fermeture_matin'],
                    heure_ouverture_apres_midi=d['heure_ouverture_apres_midi'],
                    heure_fermeture_apres_midi=d['heure_fermeture_apres_midi'],
                )
            elif demande.type_action == 'update':
                Site.objects.filter(pk=demande.cible_id).update(
                    nom=d['nom'], adresse=d.get('adresse', ''),
                    heure_ouverture_matin=d['heure_ouverture_matin'],
                    heure_fermeture_matin=d['heure_fermeture_matin'],
                    heure_ouverture_apres_midi=d['heure_ouverture_apres_midi'],
                    heure_fermeture_apres_midi=d['heure_fermeture_apres_midi'],
                )
            elif demande.type_action == 'delete':
                Site.objects.filter(pk=demande.cible_id).delete()

        elif demande.cible == 'poste':
            if demande.type_action == 'create':
                Poste.objects.create(
                    nom=d['nom'],
                    description=d.get('description', ''),
                    couleur=d.get('couleur', '#4361ee')
                )
            elif demande.type_action == 'update':
                Poste.objects.filter(pk=demande.cible_id).update(
                    nom=d['nom'],
                    description=d.get('description', ''),
                    couleur=d.get('couleur', '#4361ee')
                )
            elif demande.type_action == 'delete':
                Poste.objects.filter(pk=demande.cible_id).delete()


# ============================================================
# POSTE
# ============================================================

@admin.register(Poste)
class PosteAdmin(admin.ModelAdmin):
    list_display  = ('nom', 'description', 'couleur_display')
    search_fields = ('nom', 'description')
    ordering      = ('nom',)

    def couleur_display(self, obj):
        return mark_safe(
            f'<span style="display:inline-block;width:20px;height:20px;'
            f'background-color:{obj.couleur};border:1px solid rgba(255,255,255,.2);'
            f'border-radius:4px;vertical-align:middle;margin-right:6px"></span>{obj.couleur}'
        )
    couleur_display.short_description = 'Couleur'


# ============================================================
# SITE
# ============================================================

@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display  = ('nom', 'adresse', 'heure_ouverture_matin', 'heure_fermeture_matin')
    search_fields = ('nom', 'adresse')


# ============================================================
# EMPLOYÉ
# ============================================================

@admin.register(Employe)
class EmployeAdmin(admin.ModelAdmin):
    list_display    = ('matricule', 'nom', 'prenom', 'get_poste', 'actif', 'qr_code_preview', 'date_creation')
    list_filter     = ('poste', 'actif', 'date_creation')
    search_fields   = ('nom', 'prenom', 'matricule', 'poste__nom')
    readonly_fields = ('qr_code_token', 'date_creation', 'qr_code_display', 'info_qr_code')
    ordering        = ('matricule',)
    actions         = ['regenerer_qr_codes', 'activer_employes', 'desactiver_employes']

    fieldsets = (
        ('Informations personnelles', {
            'fields': ('nom', 'prenom', 'matricule', 'poste', 'actif')
        }),
        ('QR Code', {
            'fields': ('info_qr_code', 'qr_code_display', 'qr_code_token'),
            'classes': ('wide',),
            'description': "Gestion du QR code de l'employé"
        }),
        ('Dates', {
            'fields': ('date_creation',),
            'classes': ('collapse',),
        }),
    )

    def qr_code_preview(self, obj):
        if obj.qr_code:
            return mark_safe(
                f'<a href="{obj.qr_code.url}" target="_blank">'
                f'<img src="{obj.qr_code.url}" width="40" height="40" '
                f'style="border:1px solid rgba(255,255,255,.15);border-radius:4px;">'
                f'</a>'
            )
        return mark_safe('<span style="color:#f87171;font-size:12px;">Non généré</span>')
    qr_code_preview.short_description = 'QR Code'

    def qr_code_display(self, obj):
        if obj.qr_code:
            return mark_safe(
                f'<div style="text-align:center;margin:20px 0;">'
                f'<div style="margin-bottom:12px;font-weight:600;color:#e8eaf0;">QR Code pour le pointage</div>'
                f'<img src="{obj.qr_code.url}" width="220" height="220" '
                f'style="border:3px solid #4f8ef7;border-radius:10px;padding:10px;background:white;">'
                f'</div>'
            )
        return mark_safe(
            '<div style="color:#f87171;padding:14px;background:rgba(248,113,113,.1);'
            'border-radius:8px;text-align:center;">Le QR Code n\'a pas encore été généré.</div>'
        )
    qr_code_display.short_description = 'Visualisation du QR Code'

    def info_qr_code(self, obj):
        if obj.qr_code:
            return mark_safe(
                f'<div style="background:rgba(79,142,247,.08);padding:16px;border-radius:8px;'
                f'border:1px solid rgba(79,142,247,.2);margin-bottom:14px;">'
                f'<h4 style="margin-top:0;color:#4f8ef7;font-size:13px;font-weight:600;">'
                f'Informations du QR Code</h4>'
                f'<div style="margin-bottom:10px;font-size:12px;color:rgba(232,234,240,.6);">'
                f'Données encodées :</div>'
                f'<code style="background:rgba(255,255,255,.07);padding:6px 10px;border-radius:5px;'
                f'font-size:12px;color:#e8eaf0;display:inline-block;margin-bottom:14px;">'
                f'EMPLOYE:{obj.matricule}:{obj.qr_code_token}</code>'
                f'<div style="display:flex;gap:8px;flex-wrap:wrap;">'
                f'<a href="{obj.qr_code.url}" download class="button" style="text-decoration:none;">'
                f'Télécharger</a>'
                f'<a href="{obj.qr_code.url}" target="_blank" class="button" style="text-decoration:none;">'
                f'Ouvrir</a>'
                f'<button type="submit" name="_generate_qr" value="1" class="button" '
                f'style="background:#28a745;border-color:#28a745;">Régénérer</button>'
                f'</div></div>'
            )
        return mark_safe(
            '<div style="background:rgba(251,191,36,.08);padding:14px;border-radius:8px;'
            'border:1px solid rgba(251,191,36,.2);margin-bottom:14px;">'
            '<h4 style="margin-top:0;color:#fbbf24;font-size:13px;font-weight:600;">QR Code non généré</h4>'
            '<p style="margin-bottom:12px;font-size:13px;color:rgba(232,234,240,.6);">'
            "Le QR code n'a pas encore été généré pour cet employé.</p>"
            '<button type="submit" name="_generate_qr" value="1" class="button" '
            'style="background:#4f8ef7;border-color:#4f8ef7;color:white;">Générer QR Code</button>'
            '</div>'
        )
    info_qr_code.short_description = 'Actions QR Code'

    def get_poste(self, obj):
        return obj.poste.nom if obj.poste else "Non défini"
    get_poste.short_description = 'Poste'

    def response_change(self, request, obj):
        if "_generate_qr" in request.POST:
            obj.qr_code_token = uuid.uuid4()
            obj.generer_qr_code()
            obj.save()
            self.message_user(request, "✅ QR code régénéré avec succès !", messages.SUCCESS)
            return HttpResponseRedirect(".")
        return super().response_change(request, obj)

    def regenerer_qr_codes(self, request, queryset):
        count = 0
        for employe in queryset:
            employe.qr_code_token = uuid.uuid4()
            employe.generer_qr_code()
            employe.save()
            count += 1
        self.message_user(request, f"✅ {count} QR code(s) régénéré(s).", messages.SUCCESS)
    regenerer_qr_codes.short_description = "🔄 Régénérer les QR codes sélectionnés"

    def activer_employes(self, request, queryset):
        updated = queryset.update(actif=True)
        self.message_user(request, f"✅ {updated} employé(s) activé(s).", messages.SUCCESS)
    activer_employes.short_description = "✅ Activer les employés sélectionnés"

    def desactiver_employes(self, request, queryset):
        updated = queryset.update(actif=False)
        self.message_user(request, f"⛔ {updated} employé(s) désactivé(s).", messages.SUCCESS)
    desactiver_employes.short_description = "⛔ Désactiver les employés sélectionnés"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('poste')

    class Media:
        css = {
            'all': ('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css',)
        }


# ============================================================
# POINTAGE
# ============================================================

@admin.register(Pointage)
class PointageAdmin(admin.ModelAdmin):
    list_display    = ('employe', 'site', 'date_pointage', 'periode', 'type_journee', 'statut',
                       'heure_arrivee', 'heure_depart', 'format_retard', 'format_heures_travaillees')
    list_filter     = ('statut', 'site', 'date_pointage', 'periode', 'type_journee')
    search_fields   = ('employe__nom', 'employe__prenom', 'employe__matricule')
    readonly_fields = ('date_creation', 'date_modification', 'retard', 'heures_travaillees')
    date_hierarchy  = 'date_pointage'

    def format_retard(self, obj):
        if obj.retard and obj.retard.total_seconds() > 0:
            total_seconds = obj.retard.total_seconds()
            hours   = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = int(total_seconds % 60)
            if hours > 0 or minutes > 0:
                return f"{hours}h{minutes:02d}"
            return f"{seconds}s"
        return "-"
    format_retard.short_description = 'Retard'

    def format_heures_travaillees(self, obj):
        if obj.heures_travaillees and obj.heures_travaillees.total_seconds() > 0:
            total_seconds = obj.heures_travaillees.total_seconds()
            hours   = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            return f"{hours}h{minutes:02d}"
        return "-"
    format_heures_travaillees.short_description = 'Heures travaillées'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('employe', 'site')


# ============================================================
# SCAN
# ============================================================

@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display    = ('employe', 'site', 'timestamp_local', 'type_scan_display', 'get_pointage_info')
    list_filter     = ('type_scan', 'site', 'timestamp')
    search_fields   = ('employe__nom', 'employe__prenom', 'employe__matricule')
    readonly_fields = ('timestamp', 'timestamp_local_display')
    date_hierarchy  = 'timestamp'

    def timestamp_local(self, obj):
        return obj.get_timestamp_local().strftime('%d/%m/%Y %H:%M:%S')
    timestamp_local.short_description = 'Heure locale'

    def timestamp_local_display(self, obj):
        return obj.get_timestamp_local().strftime('%d/%m/%Y %H:%M:%S')
    timestamp_local_display.short_description = 'Heure locale'

    def get_pointage_info(self, obj):
        if obj.pointage:
            return f"{obj.pointage.get_periode_display()} - {obj.pointage.date_pointage}"
        return "-"
    get_pointage_info.short_description = 'Pointage associé'

    def type_scan_display(self, obj):
        colors = {
            'entree_matin':      '#4f8ef7',
            'sortie_matin':      '#4ade80',
            'entree_apres_midi': '#fbbf24',
            'sortie_apres_midi': '#22d3ee',
            'debut_garde':       '#a78bfa',
            'fin_garde':         '#94a3b8',
        }
        color = colors.get(obj.type_scan, '#94a3b8')
        return mark_safe(
            f'<span style="background:rgba(255,255,255,.07);color:{color};'
            f'padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;'
            f'letter-spacing:.05em;border:1px solid {color}40">'
            f'{obj.get_type_scan_display()}</span>'
        )
    type_scan_display.short_description = 'Type de scan'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('employe', 'site', 'pointage')


# ============================================================
# ALERTE RH
# ============================================================

@admin.register(AlerteRH)
class AlerteRHAdmin(admin.ModelAdmin):
    list_display  = ('employe', 'type_badge', 'detail_court', 'timestamp_local', 'traitee')
    list_filter   = ('type', 'traitee', 'timestamp')
    search_fields = ('employe__nom', 'employe__prenom', 'employe__matricule', 'detail')
    readonly_fields = ('employe', 'type', 'detail', 'timestamp', 'traitee_par', 'date_traitement')
    date_hierarchy = 'timestamp'
    actions = ['marquer_traitees']

    TYPE_COLORS = {
        'QR_INVALIDE':          ('#f87171', 'rgba(248,113,113,.12)'),
        'SITE_NON_AUTORISE':    ('#f87171', 'rgba(248,113,113,.12)'),
        'HORS_PLAGE':           ('#fbbf24', 'rgba(251,191,36,.12)'),
        'SCAN_EXCESS':          ('#fbbf24', 'rgba(251,191,36,.12)'),
        'SCAN_MANQUANT':        ('#fbbf24', 'rgba(251,191,36,.12)'),
        'DOUBLON':              ('#94a3b8', 'rgba(148,163,184,.12)'),
        'SORTIE_ANTICIPEE':     ('#4ade80', 'rgba(74,222,128,.12)'),
        'SORTIE_NON_AUTORISEE': ('#f87171', 'rgba(248,113,113,.12)'),
    }

    def type_badge(self, obj):
        color, bg = self.TYPE_COLORS.get(obj.type, ('#94a3b8', 'rgba(148,163,184,.12)'))
        return mark_safe(
            f'<span style="background:{bg};color:{color};padding:3px 10px;'
            f'border-radius:20px;font-size:11px;font-weight:600;white-space:nowrap;">'
            f'{obj.get_type_display()}</span>'
        )
    type_badge.short_description = 'Type'

    def detail_court(self, obj):
        return (obj.detail[:80] + '…') if len(obj.detail) > 80 else obj.detail
    detail_court.short_description = 'Détail'

    def timestamp_local(self, obj):
        from django.utils import timezone as tz
        local = tz.localtime(obj.timestamp)
        return local.strftime('%d/%m/%Y %H:%M')
    timestamp_local.short_description = 'Date/Heure'

    @admin.action(description='✅ Marquer comme traitées')
    def marquer_traitees(self, request, queryset):
        updated = queryset.update(traitee=True, traitee_par=request.user,
                                   date_traitement=timezone.now())
        self.message_user(request, f'✅ {updated} alerte(s) marquée(s) comme traitée(s).')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('employe')


# ============================================================
# AUTORISATION DE SORTIE ANTICIPÉE
# ============================================================

@admin.register(AutorisationSortie)
class AutorisationSortieAdmin(admin.ModelAdmin):
    list_display  = ('employe', 'periode_display', 'statut_badge',
                     'date_utilisation_local', 'heure_depart_reel', 'confirme_par')
    list_filter   = ('utilisee', 'annee', 'mois')
    search_fields = ('employe__nom', 'employe__prenom', 'employe__matricule')
    readonly_fields = ('employe', 'mois', 'annee', 'date_utilisation',
                       'heure_depart_reel', 'pointage', 'confirme_par')
    ordering = ('-annee', '-mois', 'employe__nom')

    fieldsets = (
        ('Employé', {'fields': ('employe',)}),
        ('Période', {'fields': ('mois', 'annee')}),
        ('Utilisation', {'fields': ('utilisee', 'date_utilisation', 'heure_depart_reel',
                                    'pointage', 'confirme_par')}),
        ('Note', {'fields': ('note',)}),
    )

    def periode_display(self, obj):
        return f'{obj.mois:02d}/{obj.annee}'
    periode_display.short_description = 'Mois/Année'

    def statut_badge(self, obj):
        if obj.utilisee:
            return mark_safe(
                '<span style="background:rgba(248,113,113,.12);color:#f87171;'
                'padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;">'
                '✗ Épuisée</span>'
            )
        return mark_safe(
            '<span style="background:rgba(74,222,128,.12);color:#4ade80;'
            'padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;">'
            '✓ Disponible</span>'
        )
    statut_badge.short_description = 'Statut'

    def date_utilisation_local(self, obj):
        if not obj.date_utilisation:
            return '—'
        from django.utils import timezone as tz
        local = tz.localtime(obj.date_utilisation)
        return local.strftime('%d/%m/%Y %H:%M')
    date_utilisation_local.short_description = 'Date utilisation'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('employe', 'confirme_par')


# ============================================================
# CONFIGURATION DU SITE ADMIN
# ============================================================

admin.site.site_header = "Pointage QR — Administration"
admin.site.site_title  = "Pointage QR"
admin.site.index_title = "Tableau de bord d'administration"