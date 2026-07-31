# pointage/admin.py

from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.utils.safestring import mark_safe
from django.utils.html import format_html, escape
from django.urls import path
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from django.shortcuts import render
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
import json
from .models import (
    Employe, Site, Pointage, Scan, Poste,
    CustomUser, DemandeModification,
    AnomaliePointage, AnomalieTraitement,
)
from .anomalies import marquer_traitee, marquer_cloturee
import uuid
from datetime import timedelta, datetime


# ============================================================
# FILTRES PERSONNALISÉS POUR JAZZMIN
# ============================================================

class DateDebutFilter(SimpleListFilter):
    title = 'Date début'
    parameter_name = 'date_debut'

    def lookups(self, request, model_admin):
        today = timezone.localtime(timezone.now()).date()
        return [
            ('today', "Aujourd'hui"),
            ('yesterday', 'Hier'),
            ('week', 'Cette semaine'),
            ('month', 'Ce mois-ci'),
        ]

    def queryset(self, request, queryset):
        today = timezone.localtime(timezone.now()).date()
        if self.value() == 'today':
            return queryset.filter(date_pointage=today)
        if self.value() == 'yesterday':
            yesterday = today - timedelta(days=1)
            return queryset.filter(date_pointage=yesterday)
        if self.value() == 'week':
            start_of_week = today - timedelta(days=today.weekday())
            return queryset.filter(date_pointage__gte=start_of_week)
        if self.value() == 'month':
            return queryset.filter(date_pointage__month=today.month, date_pointage__year=today.year)
        return queryset


class DateFinFilter(SimpleListFilter):
    title = 'Date fin'
    parameter_name = 'date_fin'

    def lookups(self, request, model_admin):
        today = timezone.localtime(timezone.now()).date()
        return [
            ('today', "Aujourd'hui"),
            ('yesterday', 'Hier'),
            ('week', 'Cette semaine'),
            ('month', 'Ce mois-ci'),
        ]

    def queryset(self, request, queryset):
        today = timezone.localtime(timezone.now()).date()
        if self.value() == 'today':
            return queryset.filter(date_pointage=today)
        if self.value() == 'yesterday':
            yesterday = today - timedelta(days=1)
            return queryset.filter(date_pointage=yesterday)
        if self.value() == 'week':
            start_of_week = today - timedelta(days=today.weekday())
            return queryset.filter(date_pointage__gte=start_of_week)
        if self.value() == 'month':
            return queryset.filter(date_pointage__month=today.month, date_pointage__year=today.year)
        return queryset


class EmployeFilter(SimpleListFilter):
    title = 'Employé'
    parameter_name = 'employe'

    def lookups(self, request, model_admin):
        employes = Employe.objects.filter(actif=True).order_by('nom', 'prenom')
        return [(str(e.id), f"{e.prenom} {e.nom} ({e.matricule})") for e in employes]

    def queryset(self, request, queryset):
        if self.value():
            try:
                return queryset.filter(employe_id=int(self.value()))
            except ValueError:
                return queryset
        return queryset


class PeriodeTypeFilter(SimpleListFilter):
    title = 'Type de période'
    parameter_name = 'periode_type'

    def lookups(self, request, model_admin):
        return [
            ('jour', 'Jour (normal)'),
            ('nuit', 'Nuit (garde)'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'jour':
            return queryset.filter(type_journee='normal')
        if self.value() == 'nuit':
            return queryset.filter(type_journee='garde')
        return queryset


# ============================================================
# CUSTOM USER
# ============================================================

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)

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
            obj.is_staff = False
            obj.is_superuser = False
        super().save_model(request, obj, form, change)


# ============================================================
# POSTE
# ============================================================

@admin.register(Poste)
class PosteAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description', 'couleur_display')
    search_fields = ('nom', 'description')
    ordering = ('nom',)

    def couleur_display(self, obj):
        return format_html(
            '<span style="display:inline-block;width:20px;height:20px;'
            'background-color:{};border:1px solid rgba(255,255,255,.2);'
            'border-radius:4px;vertical-align:middle;margin-right:6px"></span>{}',
            obj.couleur, obj.couleur
        )
    couleur_display.short_description = 'Couleur'


# ============================================================
# SITE
# ============================================================

@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ('nom', 'adresse', 'heure_ouverture_matin', 'heure_fermeture_matin')
    search_fields = ('nom', 'adresse')


# ============================================================
# EMPLOYÉ
# ============================================================

@admin.register(Employe)
class EmployeAdmin(admin.ModelAdmin):
    list_display = ('matricule', 'nom', 'prenom', 'get_poste', 'actif', 'qr_code_preview', 'date_creation')
    list_filter = ('poste', 'actif', 'date_creation')
    search_fields = ('nom', 'prenom', 'matricule', 'poste__nom')
    readonly_fields = ('qr_code_token', 'date_creation', 'qr_code_display', 'info_qr_code')
    ordering = ('matricule',)
    actions = ['regenerer_qr_codes', 'activer_employes', 'desactiver_employes']

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
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" width="40" height="40" '
                'style="border:1px solid rgba(255,255,255,.15);border-radius:4px;">'
                '</a>',
                obj.qr_code.url, obj.qr_code.url
            )
        return mark_safe('<span style="color:#f87171;font-size:12px;">Non généré</span>')
    qr_code_preview.short_description = 'QR Code'

    def qr_code_display(self, obj):
        if obj.qr_code:
            return format_html(
                '<div style="text-align:center;margin:20px 0;">'
                '<div style="margin-bottom:12px;font-weight:600;color:#e8eaf0;">QR Code pour le pointage</div>'
                '<img src="{}" width="220" height="220" '
                'style="border:3px solid #4f8ef7;border-radius:10px;padding:10px;background:white;">'
                '</div>',
                obj.qr_code.url
            )
        return mark_safe(
            '<div style="color:#f87171;padding:14px;background:rgba(248,113,113,.1);'
            'border-radius:8px;text-align:center;">Le QR Code n\'a pas encore été généré.</div>'
        )
    qr_code_display.short_description = 'Visualisation du QR Code'

    def info_qr_code(self, obj):
        if obj.qr_code:
            return format_html(
                '<div style="background:rgba(79,142,247,.08);padding:16px;border-radius:8px;'
                'border:1px solid rgba(79,142,247,.2);margin-bottom:14px;">'
                '<h4 style="margin-top:0;color:#4f8ef7;font-size:13px;font-weight:600;">'
                'Informations du QR Code</h4>'
                '<div style="margin-bottom:10px;font-size:12px;color:rgba(232,234,240,.6);">'
                'Données encodées :</div>'
                '<code style="background:rgba(255,255,255,.07);padding:6px 10px;border-radius:5px;'
                'font-size:12px;color:#e8eaf0;display:inline-block;margin-bottom:14px;">'
                'EMPLOYE:{}:{}</code>'
                '<div style="display:flex;gap:8px;flex-wrap:wrap;">'
                '<a href="{}" download class="button" style="text-decoration:none;">'
                'Télécharger</a>'
                '<a href="{}" target="_blank" class="button" style="text-decoration:none;">'
                'Ouvrir</a>'
                '<button type="submit" name="_generate_qr" value="1" class="button" '
                'style="background:#28a745;border-color:#28a745;">Régénérer</button>'
                '</div></div>',
                obj.matricule, obj.qr_code_token, obj.qr_code.url, obj.qr_code.url
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
# POINTAGE - VERSION AMÉLIORÉE AVEC FILTRES PERSONNALISÉS
# ============================================================

@admin.register(Pointage)
class PointageAdmin(admin.ModelAdmin):
    # ============================================================
    # CONFIGURATION DE BASE
    # ============================================================
    
    change_list_template = "admin/pointage/pointage_changelist.html"
    
    list_display = [
        'id',
        'employe',
        'date_pointage',
        'periode',
        'type_journee',
        'heure_arrivee',
        'heure_depart',
        'site',
        'statut',
        'get_retard_display',
        'get_heures_display',
        'date_creation',
    ]
    
    # ============================================================
    # FILTRES - INCLURE LES FILTRES PERSONNALISÉS
    # ============================================================
    list_filter = [
        DateDebutFilter,
        DateFinFilter,
        EmployeFilter,
        PeriodeTypeFilter,
        'statut',
        'periode',
        'site',
        'type_journee',
    ]
    
    search_fields = [
        'employe__nom',
        'employe__prenom',
        'employe__matricule',
        'site__nom',
    ]
    
    readonly_fields = ('date_creation', 'date_modification', 'retard', 'heures_travaillees')
    date_hierarchy = 'date_pointage'
    
    # ============================================================
    # CHAMPS PERSONNALISÉS
    # ============================================================
    
    def get_retard_display(self, obj):
        if obj.retard and obj.retard.total_seconds() > 0:
            minutes = obj.get_retard_minutes()
            if minutes >= 30:
                return format_html(
                    '<span style="background:#FEE2E2;color:#B91C1C;padding:2px 10px;border-radius:9999px;font-weight:600;font-size:10px;">⚠️ {} min</span>',
                    minutes
                )
            elif minutes >= 15:
                return format_html(
                    '<span style="background:#FEF3C7;color:#B45309;padding:2px 10px;border-radius:9999px;font-weight:600;font-size:10px;">⏱️ {} min</span>',
                    minutes
                )
            return f"{minutes} min"
        return "—"
    get_retard_display.short_description = "Retard"
    
    def get_heures_display(self, obj):
        if obj.heures_travaillees and obj.heures_travaillees.total_seconds() > 0:
            total_seconds = obj.heures_travaillees.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            return f"{hours}h{minutes:02d}"
        return "—"
    get_heures_display.short_description = "Heures travaillées"
    
    # ============================================================
    # ACTIONS EN MASSE
    # ============================================================
    
    actions = ['marquer_present', 'marquer_retard', 'marquer_absent', 'supprimer_selection']
    
    def marquer_present(self, request, queryset):
        queryset.update(statut='present')
        self.message_user(request, f"✅ {queryset.count()} pointage(s) marqué(s) comme présent.")
    marquer_present.short_description = "✅ Marquer comme présent"
    
    def marquer_retard(self, request, queryset):
        queryset.update(statut='retard')
        self.message_user(request, f"⚠️ {queryset.count()} pointage(s) marqué(s) comme retard.")
    marquer_retard.short_description = "⚠️ Marquer comme retard"
    
    def marquer_absent(self, request, queryset):
        queryset.update(statut='absent')
        self.message_user(request, f"❌ {queryset.count()} pointage(s) marqué(s) comme absent.")
    marquer_absent.short_description = "❌ Marquer comme absent"
    
    def supprimer_selection(self, request, queryset):
        count = queryset.count()
        if count > 0:
            queryset.delete()
            self.message_user(request, f"🗑️ {count} pointage(s) supprimé(s).")
    supprimer_selection.short_description = "🗑️ Supprimer la sélection"
    
    # ============================================================
    # GET QUERYSET
    # ============================================================
    
    def get_queryset(self, request):
        return Pointage.objects.select_related('employe', 'site')
    
    # ============================================================
    # CHANGELIST VIEW - POUR LE CONTEXTE DU TEMPLATE
    # ============================================================
    
    def changelist_view(self, request, extra_context=None):
        # Récupérer le queryset via Django Admin (les filtres sont déjà appliqués)
        cl = self.get_changelist_instance(request)
        queryset = cl.get_queryset(request)
        
        # Vérifier l'export Excel
        if 'export_excel' in request.GET:
            return self.export_excel(request, queryset)
        
        # Statistiques
        total = queryset.count()
        presents = queryset.filter(statut='present').count()
        retards = queryset.filter(statut='retard').count()
        absents = queryset.filter(statut='absent').count()
        anomalies = queryset.filter(
            Q(retard__gte=timedelta(minutes=30)) |
            Q(statut='absent')
        ).count()
        
        total_heures = timedelta()
        for p in queryset[:100]:
            if p.heures_travaillees:
                total_heures += p.heures_travaillees
        
        # Listes pour les filtres (si nécessaire dans le template)
        sites_list = Site.objects.all().order_by('nom')
        employes_list = Employe.objects.filter(actif=True).order_by('nom', 'prenom')
        
        extra_context = extra_context or {}
        extra_context.update({
            'total': total,
            'presents_count': presents,
            'retards_count': retards,
            'absents_count': absents,
            'anomalies_count': anomalies,
            'total_heures': self._format_timedelta(total_heures),
            'employes_count': queryset.values('employe').distinct().count(),
            'total_employes': Employe.objects.filter(actif=True).count(),
            'sites_list': sites_list,
            'employes_list': employes_list,
        })
        
        return super().changelist_view(request, extra_context=extra_context)
    
    def _format_timedelta(self, td):
        if td and td.total_seconds() > 0:
            total_seconds = td.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            return f"{hours}h{minutes:02d}"
        return "0h00"
    
    # ============================================================
    # EXPORT EXCEL
    # ============================================================
    
    def export_excel(self, request, queryset):
        """Exporte les pointages en Excel"""
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from django.http import HttpResponse
        
        if not queryset.exists():
            messages.warning(request, "Aucun pointage à exporter.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/admin/pointage/pointage/'))
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Pointages"
        
        # Couleurs
        BLUE = '1E3A5F'
        TOTAL_BG = 'EEF2FF'
        
        # En-têtes
        headers = ['Employé', 'Matricule', 'Date', 'Période', 'Type', 'Arrivée', 'Départ', 'Site', 'Statut', 'Retard (min)', 'Heures']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color=BLUE, end_color=BLUE, fill_type="solid")
            cell.alignment = Alignment(horizontal="center")
        
        # Données
        for row, pointage in enumerate(queryset, 2):
            ws.cell(row=row, column=1, value=str(pointage.employe))
            ws.cell(row=row, column=2, value=pointage.employe.matricule)
            ws.cell(row=row, column=3, value=pointage.date_pointage.strftime('%d/%m/%Y'))
            ws.cell(row=row, column=4, value=pointage.get_periode_display())
            ws.cell(row=row, column=5, value=pointage.get_type_journee_display())
            ws.cell(row=row, column=6, value=pointage.heure_arrivee.strftime('%H:%M') if pointage.heure_arrivee else '')
            ws.cell(row=row, column=7, value=pointage.heure_depart.strftime('%H:%M') if pointage.heure_depart else '')
            ws.cell(row=row, column=8, value=str(pointage.site) if pointage.site else '')
            ws.cell(row=row, column=9, value=pointage.get_statut_display())
            
            retard_minutes = pointage.get_retard_minutes() if pointage.retard else 0
            ws.cell(row=row, column=10, value=retard_minutes)
            
            if pointage.heures_travaillees and pointage.heures_travaillees.total_seconds() > 0:
                total_seconds = pointage.heures_travaillees.total_seconds()
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                ws.cell(row=row, column=11, value=f"{hours}h{minutes:02d}")
            else:
                ws.cell(row=row, column=11, value="0h00")
        
        # Ajuster les colonnes
        for col in range(1, len(headers) + 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 18
        
        # Total
        total_row = queryset.count() + 2
        ws.cell(row=total_row, column=1, value="TOTAL").font = Font(bold=True)
        ws.cell(row=total_row, column=10, value=queryset.filter(retard__gt=timedelta(0)).count())
        ws.cell(row=total_row, column=1).fill = PatternFill('solid', start_color=TOTAL_BG)
        ws.cell(row=total_row, column=10).fill = PatternFill('solid', start_color=TOTAL_BG)
        
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f"pointages_export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response


# ============================================================
# SCAN
# ============================================================

@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display = ('employe', 'site', 'timestamp_local', 'type_scan_display', 'get_pointage_info')
    list_filter = ('type_scan', 'site', 'timestamp')
    search_fields = ('employe__nom', 'employe__prenom', 'employe__matricule')
    readonly_fields = ('timestamp', 'timestamp_local_display')
    date_hierarchy = 'timestamp'

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
            'entree_matin': '#4f8ef7',
            'sortie_matin': '#4ade80',
            'entree_apres_midi': '#fbbf24',
            'sortie_apres_midi': '#22d3ee',
            'debut_garde': '#a78bfa',
            'fin_garde': '#94a3b8',
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
# DEMANDE DE MODIFICATION
# ============================================================

@admin.register(DemandeModification)
class DemandeModificationAdmin(admin.ModelAdmin):
    list_display = ('demandeur', 'type_action', 'cible', 'statut_badge', 'date_creation', 'boutons_action')
    list_filter = ('statut', 'type_action', 'cible')
    search_fields = ('demandeur__username',)
    actions = ['approuver_demandes', 'refuser_demandes']

    readonly_fields = (
        'demandeur', 'type_action', 'cible',
        'donnees_formatees', 'statut_badge',
        'date_creation', 'traitee_par', 'date_traitement',
        'boutons_fiche',
    )

    fieldsets = (
        ('Informations', {
            'fields': ('demandeur', 'type_action', 'cible', 'date_creation')
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

    def statut_badge(self, obj):
        styles = {
            'en_attente': ('rgba(251,191,36,.12)', '#fbbf24', '⏳ En attente'),
            'approuvee': ('rgba(74,222,128,.12)', '#4ade80', '✅ Approuvée'),
            'refusee': ('rgba(248,113,113,.12)', '#f87171', '❌ Refusée'),
        }
        bg, color, label = styles.get(obj.statut, ('rgba(255,255,255,.07)', '#e8eaf0', obj.statut))
        return mark_safe(
            f'<span style="background:{bg};color:{color};padding:4px 12px;'
            f'border-radius:20px;font-size:12px;font-weight:600;white-space:nowrap;">'
            f'{label}</span>'
        )
    statut_badge.short_description = 'Statut'

    def boutons_action(self, obj):
        from django.urls import reverse
        if obj.statut != 'en_attente':
            return mark_safe(
                '<span style="color:rgba(232,234,240,.3);font-size:12px;font-style:italic;">Traitée</span>'
            )
        url_approuver = reverse('admin:demande_approuver', args=[obj.pk])
        url_refuser = reverse('admin:demande_refuser', args=[obj.pk])
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

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('<int:pk>/approuver/', self.admin_site.admin_view(self.approuver_view), name='demande_approuver'),
            path('<int:pk>/refuser/', self.admin_site.admin_view(self.refuser_view), name='demande_refuser'),
        ]
        return custom + urls

    def approuver_view(self, request, pk):
        from django.shortcuts import get_object_or_404
        demande = get_object_or_404(DemandeModification, pk=pk)
        if demande.statut == 'en_attente':
            try:
                self._appliquer_demande(demande)
                demande.statut = 'approuvee'
                demande.traitee_par = request.user
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
            demande.statut = 'refusee'
            demande.traitee_par = request.user
            demande.date_traitement = timezone.now()
            demande.save()
            self.message_user(request, f"❌ Demande #{pk} refusée.")
        return HttpResponseRedirect("../../")

    def response_change(self, request, obj):
        if '_accepter' in request.POST and obj.statut == 'en_attente':
            try:
                self._appliquer_demande(obj)
                obj.statut = 'approuvee'
                obj.traitee_par = request.user
                obj.date_traitement = timezone.now()
                obj.save()
                self.message_user(request, f"✅ Demande #{obj.pk} approuvée et appliquée.")
            except Exception as e:
                self.message_user(request, f"❌ Erreur : {e}", level='error')
            return HttpResponseRedirect("../")

        if '_refuser' in request.POST and obj.statut == 'en_attente':
            obj.statut = 'refusee'
            obj.traitee_par = request.user
            obj.date_traitement = timezone.now()
            obj.save()
            self.message_user(request, f"❌ Demande #{obj.pk} refusée.")
            return HttpResponseRedirect("../")

        return super().response_change(request, obj)

    def save_model(self, request, obj, form, change):
        if change:
            original = DemandeModification.objects.get(pk=obj.pk)
            obj.demandeur = original.demandeur
            obj.type_action = original.type_action
            obj.cible = original.cible
            obj.cible_id = original.cible_id
            obj.donnees = original.donnees
            obj.statut = original.statut
            obj.traitee_par = original.traitee_par
            obj.date_traitement = original.date_traitement
        super().save_model(request, obj, form, change)

    def donnees_formatees(self, obj):
        if not obj.donnees:
            return '—'
        lignes = []
        for cle, valeur in obj.donnees.items():
            lignes.append(format_html(
                '<tr>'
                '<td style="padding:8px 14px;color:rgba(255,255,255,.45);font-size:11px;'
                'text-transform:uppercase;letter-spacing:.08em;white-space:nowrap;'
                'border-bottom:1px solid rgba(255,255,255,.06)">{}</td>'
                '<td style="padding:8px 14px;font-weight:500;color:#e8eaf0;'
                'border-bottom:1px solid rgba(255,255,255,.06)">{}</td>'
                '</tr>',
                cle, valeur
            ))
        return format_html(
            '<table style="border-collapse:collapse;width:100%;background:#1c2236;'
            'border-radius:8px;overflow:hidden;border:1px solid rgba(255,255,255,.07)">{}</table>',
            mark_safe(''.join(lignes))
        )
    donnees_formatees.short_description = "Données de la demande"

    @admin.action(description="✅ Approuver les demandes sélectionnées")
    def approuver_demandes(self, request, queryset):
        for demande in queryset.filter(statut='en_attente'):
            try:
                self._appliquer_demande(demande)
                demande.statut = 'approuvee'
                demande.traitee_par = request.user
                demande.date_traitement = timezone.now()
                demande.save()
            except Exception as e:
                self.message_user(request, f"❌ Erreur demande #{demande.pk} : {e}", level='error')
        self.message_user(request, "✅ Demandes approuvées et appliquées.")

    @admin.action(description="❌ Refuser les demandes sélectionnées")
    def refuser_demandes(self, request, queryset):
        for demande in queryset.filter(statut='en_attente'):
            demande.statut = 'refusee'
            demande.traitee_par = request.user
            demande.date_traitement = timezone.now()
            demande.save()
        self.message_user(request, "❌ Demandes refusées.")

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
# ANOMALIES DE POINTAGE
# ============================================================

class AnomalieTraitementInline(admin.StackedInline):
    model = AnomalieTraitement
    can_delete = False
    extra = 0
    max_num = 1
    fields = ('administrateur', 'date_traitement', 'commentaire', 'pointage_concerne', 'corrections')
    readonly_fields = ('administrateur', 'date_traitement')


@admin.register(AnomaliePointage)
class AnomaliePointageAdmin(admin.ModelAdmin):
    list_display = ('type_display', 'employe_ou_matricule', 'gravite_badge', 'statut_badge', 'site', 'date_pointage', 'created_at')
    list_filter = ('statut', 'type', 'site')
    search_fields = ('employe__nom', 'employe__prenom', 'employe__matricule', 'matricule_scanne', 'message')
    date_hierarchy = 'created_at'
    inlines = [AnomalieTraitementInline]
    actions = ['marquer_traitees', 'marquer_cloturees']
    ordering = ('-created_at',)

    readonly_fields = (
        'type', 'employe', 'matricule_scanne', 'site', 'date_pointage',
        'message', 'contexte_formate', 'gravite_badge', 'statut_badge',
        'cloturee_par', 'date_cloture', 'created_at',
    )

    fieldsets = (
        ("Anomalie détectée", {
            'fields': ('type', 'gravite_badge', 'employe', 'matricule_scanne', 'site', 'date_pointage', 'created_at')
        }),
        ("Détails", {'fields': ('message', 'contexte_formate')}),
        ("Statut", {'fields': ('statut_badge', 'cloturee_par', 'date_cloture')}),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def type_display(self, obj):
        return obj.get_type_display()
    type_display.short_description = 'Type'
    type_display.admin_order_field = 'type'

    def employe_ou_matricule(self, obj):
        if obj.employe:
            return obj.employe.get_nom_complet()
        return obj.matricule_scanne or '—'
    employe_ou_matricule.short_description = 'Employé'

    def gravite_badge(self, obj):
        styles = {
            'info': ('rgba(96,165,250,.12)', '#60a5fa', 'ℹ️ Info'),
            'warning': ('rgba(251,191,36,.12)', '#fbbf24', '⚠️ Avertissement'),
            'critique': ('rgba(248,113,113,.12)', '#f87171', '🚨 Critique'),
        }
        bg, color, label = styles.get(obj.gravite, ('rgba(255,255,255,.07)', '#e8eaf0', obj.gravite))
        return mark_safe(
            f'<span style="background:{bg};color:{color};padding:4px 12px;'
            f'border-radius:20px;font-size:12px;font-weight:600;white-space:nowrap;">'
            f'{label}</span>'
        )
    gravite_badge.short_description = 'Gravité'

    def statut_badge(self, obj):
        styles = {
            AnomaliePointage.STATUT_OUVERTE: ('rgba(248,113,113,.12)', '#f87171', '🔴 Ouverte'),
            AnomaliePointage.STATUT_TRAITEE: ('rgba(251,191,36,.12)', '#fbbf24', '🟡 Traitée'),
            AnomaliePointage.STATUT_CLOTUREE: ('rgba(74,222,128,.12)', '#4ade80', '✅ Clôturée'),
        }
        bg, color, label = styles.get(obj.statut, ('rgba(255,255,255,.07)', '#e8eaf0', obj.statut))
        return mark_safe(
            f'<span style="background:{bg};color:{color};padding:4px 12px;'
            f'border-radius:20px;font-size:12px;font-weight:600;white-space:nowrap;">'
            f'{label}</span>'
        )
    statut_badge.short_description = 'Statut'

    def contexte_formate(self, obj):
        if not obj.contexte:
            return '—'
        return format_html(
            '<pre style="background:#1c2236;border:1px solid rgba(255,255,255,.07);'
            'border-radius:8px;padding:12px 14px;font-size:12px;color:#e8eaf0;'
            'white-space:pre-wrap;">{}</pre>',
            json.dumps(obj.contexte, indent=2, ensure_ascii=False, default=str)
        )
    contexte_formate.short_description = "Contexte (technique)"

    @admin.action(description="✅ Marquer les anomalies sélectionnées comme traitées")
    def marquer_traitees(self, request, queryset):
        count = 0
        for anomalie in queryset.exclude(statut=AnomaliePointage.STATUT_CLOTUREE):
            try:
                marquer_traitee(
                    anomalie, request.user,
                    commentaire="Marquée traitée depuis l'administration."
                )
                count += 1
            except ValueError as e:
                self.message_user(request, f"❌ Anomalie #{anomalie.pk} : {e}", level=messages.ERROR)
        self.message_user(request, f"✅ {count} anomalie(s) marquée(s) comme traitée(s).")

    @admin.action(description="🔒 Clôturer les anomalies sélectionnées")
    def marquer_cloturees(self, request, queryset):
        count = 0
        for anomalie in queryset:
            try:
                marquer_cloturee(anomalie, request.user)
                count += 1
            except ValueError as e:
                self.message_user(request, f"❌ Anomalie #{anomalie.pk} : {e}", level=messages.ERROR)
        self.message_user(request, f"🔒 {count} anomalie(s) clôturée(s).")


# ============================================================
# CONFIGURATION DU SITE ADMIN
# ============================================================

admin.site.site_header = "Pointage QR — Administration"
admin.site.site_title = "Pointage QR"
admin.site.index_title = "Tableau de bord d'administration"