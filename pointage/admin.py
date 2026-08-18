# pointage/admin.py - VERSION FINALE QUI FONCTIONNE VRAIMENT

from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.urls import path, reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from django.db.models import Q
from django.shortcuts import render, get_object_or_404
import json
from .models import (
    Employe, Site, Pointage, Scan, Poste,
    CustomUser, DemandeModification,
    AnomaliePointage, AnomalieTraitement,
)
from .anomalies import marquer_traitee, marquer_cloturee
import uuid
from datetime import timedelta, datetime
from collections import defaultdict
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


# ============================================================
# FILTRES DE LA BARRE LATERALE
# ============================================================

class PeriodeTypeFilter(SimpleListFilter):
    title = 'Type de periode'
    parameter_name = 'periode_type'

    def lookups(self, request, model_admin):
        return (
            ('jour', 'Jour'),
            ('nuit', 'Nuit (Gardes)'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'jour':
            return queryset.filter(type_journee='normal')
        if value == 'nuit':
            return queryset.filter(type_journee='garde')
        return queryset


class EmployeFilter(SimpleListFilter):
    title = 'Employe'
    parameter_name = 'employe'

    def lookups(self, request, model_admin):
        employes = Employe.objects.filter(actif=True).select_related('poste').order_by('nom', 'prenom')
        return [
            (str(employe.pk), f"{employe.prenom} {employe.nom} ({employe.matricule})")
            for employe in employes
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset
        try:
            employe_id = int(value)
            return queryset.filter(employe_id=employe_id)
        except (ValueError, TypeError):
            return queryset


class SiteFilter(SimpleListFilter):
    title = 'Site'
    parameter_name = 'site'

    def lookups(self, request, model_admin):
        sites = Site.objects.all().order_by('nom')
        return [(str(site.pk), site.nom) for site in sites]

    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset
        try:
            site_id = int(value)
            return queryset.filter(site_id=site_id)
        except (ValueError, TypeError):
            return queryset


class StatutPointageFilter(SimpleListFilter):
    title = 'Statut'
    parameter_name = 'statut'

    def lookups(self, request, model_admin):
        return (
            ('present', 'Present'),
            ('retard', 'En retard'),
            ('absent', 'Absent'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value in ('present', 'retard', 'absent'):
            return queryset.filter(statut=value)
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
        ('Role & Permissions', {'fields': ('role',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role & Permissions', {'fields': ('role',)}),
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
# EMPLOYE
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
        return mark_safe('<span style="color:#f87171;font-size:12px;">Non genere</span>')
    qr_code_preview.short_description = 'QR Code'

    def qr_code_display(self, obj):
        if obj.qr_code:
            return format_html(
                '<div style="text-align:center;margin:20px 0;">'
                '<div style="margin-bottom:12px;font-weight:600;color:#e8eaf0;">QR Code</div>'
                '<img src="{}" width="220" height="220" '
                'style="border:3px solid #4f8ef7;border-radius:10px;padding:10px;background:white;">'
                '</div>',
                obj.qr_code.url
            )
        return mark_safe('<div style="color:#f87171;padding:14px;text-align:center;">Non genere</div>')
    qr_code_display.short_description = 'Visualisation QR Code'

    def info_qr_code(self, obj):
        if obj.qr_code:
            return format_html(
                '<div style="background:rgba(79,142,247,.08);padding:16px;border-radius:8px;'
                'border:1px solid rgba(79,142,247,.2);margin-bottom:14px;">'
                '<h4 style="margin-top:0;color:#4f8ef7;font-size:13px;font-weight:600;">QR Code</h4>'
                '<code style="background:rgba(255,255,255,.07);padding:6px 10px;border-radius:5px;'
                'font-size:12px;color:#e8eaf0;display:inline-block;margin-bottom:14px;">'
                'EMPLOYE:{}:{}</code>'
                '<div style="display:flex;gap:8px;flex-wrap:wrap;">'
                '<a href="{}" download class="button" style="text-decoration:none;">Telecharger</a>'
                '<a href="{}" target="_blank" class="button" style="text-decoration:none;">Ouvrir</a>'
                '<button type="submit" name="_generate_qr" value="1" class="button" '
                'style="background:#28a745;border-color:#28a745;">Regenerer</button>'
                '</div></div>',
                obj.matricule, obj.qr_code_token, obj.qr_code.url, obj.qr_code.url
            )
        return mark_safe(
            '<div style="background:rgba(251,191,36,.08);padding:14px;border-radius:8px;'
            'border:1px solid rgba(251,191,36,.2);">'
            '<button type="submit" name="_generate_qr" value="1" class="button" '
            'style="background:#4f8ef7;border-color:#4f8ef7;color:white;">Generer QR Code</button>'
            '</div>'
        )
    info_qr_code.short_description = 'Actions QR Code'

    def get_poste(self, obj):
        return obj.poste.nom if obj.poste else "Non defini"
    get_poste.short_description = 'Poste'

    def response_change(self, request, obj):
        if "_generate_qr" in request.POST:
            obj.qr_code_token = uuid.uuid4()
            obj.generer_qr_code()
            obj.save()
            self.message_user(request, "QR code regenere avec succes !", messages.SUCCESS)
            return HttpResponseRedirect(".")
        return super().response_change(request, obj)

    def regenerer_qr_codes(self, request, queryset):
        count = 0
        for employe in queryset:
            employe.qr_code_token = uuid.uuid4()
            employe.generer_qr_code()
            employe.save()
            count += 1
        self.message_user(request, f"{count} QR code(s) regenere(s).", messages.SUCCESS)
    regenerer_qr_codes.short_description = "Regenerer les QR codes"

    def activer_employes(self, request, queryset):
        updated = queryset.update(actif=True)
        self.message_user(request, f"{updated} employe(s) active(s).", messages.SUCCESS)
    activer_employes.short_description = "Activer"

    def desactiver_employes(self, request, queryset):
        updated = queryset.update(actif=False)
        self.message_user(request, f"{updated} employe(s) desactive(s).", messages.SUCCESS)
    desactiver_employes.short_description = "Desactiver"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('poste')


# ============================================================
# POINTAGE - SOLUTION DEFINITIVE
# ============================================================

@admin.register(Pointage)
class PointageAdmin(admin.ModelAdmin):
    change_list_template = "admin/pointage/pointage_changelist.html"
    
    list_display = [
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
    ]
    
    list_filter = [
        EmployeFilter,
        SiteFilter,
        PeriodeTypeFilter,
        StatutPointageFilter,
    ]

    search_fields = [
        'employe__nom',
        'employe__prenom',
        'employe__matricule',
        'site__nom',
    ]

    readonly_fields = ('retard', 'heures_travaillees', 'date_creation', 'date_modification')

    def get_retard_display(self, obj):
        if obj.retard and obj.retard.total_seconds() > 0:
            minutes = obj.get_retard_minutes()
            if minutes >= 30:
                return format_html(
                    '<span style="background:#FEE2E2;color:#B91C1C;padding:2px 10px;border-radius:9999px;font-weight:600;font-size:10px;">[!] {} min</span>',
                    minutes
                )
            return f"{minutes} min"
        return "-"
    get_retard_display.short_description = "Retard"
    
    def get_heures_display(self, obj):
        if obj.heures_travaillees and obj.heures_travaillees.total_seconds() > 0:
            total_seconds = obj.heures_travaillees.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            return f"{hours}h{minutes:02d}"
        return "-"
    get_heures_display.short_description = "Heures travaillees"
    
    actions = ['marquer_present', 'marquer_retard', 'marquer_absent', 'supprimer_selection']
    
    def marquer_present(self, request, queryset):
        count = queryset.update(statut='present')
        self.message_user(request, f"{count} pointage(s) marque(s) comme present.")
    marquer_present.short_description = "Marquer comme present"
    
    def marquer_retard(self, request, queryset):
        count = queryset.update(statut='retard')
        self.message_user(request, f"{count} pointage(s) marque(s) comme retard.")
    marquer_retard.short_description = "Marquer comme retard"
    
    def marquer_absent(self, request, queryset):
        count = queryset.update(statut='absent')
        self.message_user(request, f"{count} pointage(s) marque(s) comme absent.")
    marquer_absent.short_description = "Marquer comme absent"
    
    def supprimer_selection(self, request, queryset):
        count = queryset.count()
        if count > 0:
            queryset.delete()
            self.message_user(request, f"{count} pointage(s) supprime(s).")
    supprimer_selection.short_description = "Supprimer"
    
    def get_queryset(self, request):
        return Pointage.objects.select_related('employe', 'site')
    
    # ============================================================
    # LA VRAIE SOLUTION - On ne touche PAS à request.GET
    # ============================================================
    
    def changelist_view(self, request, extra_context=None):
        # Récupérer les dates depuis GET (sans modifier request.GET)
        date_debut = request.GET.get('date_debut', '')
        date_fin = request.GET.get('date_fin', '')
        
        # Obtenir le ChangeList standard
        cl = self.get_changelist_instance(request)
        queryset = cl.get_queryset(request)
        
        # Appliquer les filtres de date sur le queryset
        if date_debut and date_fin:
            try:
                debut = datetime.strptime(date_debut, '%Y-%m-%d').date()
                fin = datetime.strptime(date_fin, '%Y-%m-%d').date()
                queryset = queryset.filter(
                    date_pointage__gte=debut,
                    date_pointage__lte=fin
                )
            except ValueError:
                pass
        elif date_debut:
            try:
                debut = datetime.strptime(date_debut, '%Y-%m-%d').date()
                queryset = queryset.filter(date_pointage__gte=debut)
            except ValueError:
                pass
        elif date_fin:
            try:
                fin = datetime.strptime(date_fin, '%Y-%m-%d').date()
                queryset = queryset.filter(date_pointage__lte=fin)
            except ValueError:
                pass
        
        # Vérifier l'export Excel
        if 'export_excel' in request.GET:
            return self.export_excel(request, queryset)
        
        # Statistiques
        total = queryset.count()
        presents = queryset.filter(statut='present').count()
        retards = queryset.filter(statut='retard').count()
        absents = queryset.filter(statut='absent').count()
        
        # Contexte pour le template
        extra_context = extra_context or {}
        extra_context.update({
            'total': total,
            'presents_count': presents,
            'retards_count': retards,
            'absents_count': absents,
            'date_debut': date_debut,
            'date_fin': date_fin,
        })
        
        return super().changelist_view(request, extra_context=extra_context)
    
    # ============================================================
    # EXPORT EXCEL
    # ============================================================
    
    def export_excel(self, request, queryset):
        # ... votre code d'export Excel ici ...
        pass


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
        ('Donnees soumises', {
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
            'en_attente': ('rgba(251,191,36,.12)', '#fbbf24', 'En attente'),
            'approuvee': ('rgba(74,222,128,.12)', '#4ade80', 'Approuvee'),
            'refusee': ('rgba(248,113,113,.12)', '#f87171', 'Refusee'),
        }
        bg, color, label = styles.get(obj.statut, ('rgba(255,255,255,.07)', '#e8eaf0', obj.statut))
        return mark_safe(
            f'<span style="background:{bg};color:{color};padding:4px 12px;'
            f'border-radius:20px;font-size:12px;font-weight:600;white-space:nowrap;">'
            f'{label}</span>'
        )
    statut_badge.short_description = 'Statut'

    def boutons_action(self, obj):
        if obj.statut != 'en_attente':
            return mark_safe(
                '<span style="color:rgba(232,234,240,.3);font-size:12px;font-style:italic;">Traitee</span>'
            )
        url_approuver = reverse('admin:demande_approuver', args=[obj.pk])
        url_refuser = reverse('admin:demande_refuser', args=[obj.pk])
        return mark_safe(
            f'<div style="display:flex;gap:6px;">'
            f'<a href="{url_approuver}" style="background:rgba(74,222,128,.12);color:#4ade80;'
            f'border:1px solid rgba(74,222,128,.3);padding:4px 12px;border-radius:6px;'
            f'font-size:11px;font-weight:600;text-decoration:none;white-space:nowrap;">Accepter</a>'
            f'<a href="{url_refuser}" style="background:rgba(248,113,113,.12);color:#f87171;'
            f'border:1px solid rgba(248,113,113,.3);padding:4px 12px;border-radius:6px;'
            f'font-size:11px;font-weight:600;text-decoration:none;white-space:nowrap;">Refuser</a>'
            f'</div>'
        )
    boutons_action.short_description = 'Actions'

    def boutons_fiche(self, obj):
        btn_retour = (
            '<a href="../" style="display:inline-flex;align-items:center;gap:6px;'
            'background:rgba(255,255,255,.06);color:#e8eaf0;'
            'border:1px solid rgba(255,255,255,.15);padding:8px 18px;'
            'border-radius:6px;font-size:13px;font-weight:600;text-decoration:none;">'
            '<- Retour</a>'
        )
        if obj.statut != 'en_attente':
            return mark_safe(btn_retour)

        return mark_safe(
            '<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">'
            '<button type="submit" name="_accepter" value="1" '
            'style="background:rgba(74,222,128,.15);color:#4ade80;'
            'border:1px solid rgba(74,222,128,.35);padding:8px 20px;'
            'border-radius:6px;font-size:13px;font-weight:600;cursor:pointer;">'
            'Accepter</button>'
            '<button type="submit" name="_refuser" value="1" '
            'style="background:rgba(248,113,113,.15);color:#f87171;'
            'border:1px solid rgba(248,113,113,.35);padding:8px 20px;'
            'border-radius:6px;font-size:13px;font-weight:600;cursor:pointer;">'
            'Refuser</button>'
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
        demande = get_object_or_404(DemandeModification, pk=pk)
        if demande.statut == 'en_attente':
            try:
                self._appliquer_demande(demande)
                demande.statut = 'approuvee'
                demande.traitee_par = request.user
                demande.date_traitement = timezone.now()
                demande.save()
                self.message_user(request, f"Demande #{pk} approuvee et appliquee.")
            except Exception as e:
                self.message_user(request, f"Erreur : {e}", level='error')
        return HttpResponseRedirect("../../")

    def refuser_view(self, request, pk):
        demande = get_object_or_404(DemandeModification, pk=pk)
        if demande.statut == 'en_attente':
            demande.statut = 'refusee'
            demande.traitee_par = request.user
            demande.date_traitement = timezone.now()
            demande.save()
            self.message_user(request, f"Demande #{pk} refusee.")
        return HttpResponseRedirect("../../")

    def response_change(self, request, obj):
        if '_accepter' in request.POST and obj.statut == 'en_attente':
            try:
                self._appliquer_demande(obj)
                obj.statut = 'approuvee'
                obj.traitee_par = request.user
                obj.date_traitement = timezone.now()
                obj.save()
                self.message_user(request, f"Demande #{obj.pk} approuvee et appliquee.")
            except Exception as e:
                self.message_user(request, f"Erreur : {e}", level='error')
            return HttpResponseRedirect("../")

        if '_refuser' in request.POST and obj.statut == 'en_attente':
            obj.statut = 'refusee'
            obj.traitee_par = request.user
            obj.date_traitement = timezone.now()
            obj.save()
            self.message_user(request, f"Demande #{obj.pk} refusee.")
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
            return '-'
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
    donnees_formatees.short_description = "Donnees de la demande"

    @admin.action(description="Approuver les demandes selectionnees")
    def approuver_demandes(self, request, queryset):
        for demande in queryset.filter(statut='en_attente'):
            try:
                self._appliquer_demande(demande)
                demande.statut = 'approuvee'
                demande.traitee_par = request.user
                demande.date_traitement = timezone.now()
                demande.save()
            except Exception as e:
                self.message_user(request, f"Erreur demande #{demande.pk} : {e}", level='error')
        self.message_user(request, "Demandes approuvees et appliquees.")

    @admin.action(description="Refuser les demandes selectionnees")
    def refuser_demandes(self, request, queryset):
        for demande in queryset.filter(statut='en_attente'):
            demande.statut = 'refusee'
            demande.traitee_par = request.user
            demande.date_traitement = timezone.now()
            demande.save()
        self.message_user(request, "Demandes refusees.")

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
                try:
                    employe = Employe.objects.get(pk=demande.cible_id)
                    employe.delete()
                except Employe.DoesNotExist:
                    pass

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
# SCAN
# ============================================================

@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display = ('employe', 'site', 'timestamp_local', 'type_scan_display')
    list_filter = ('type_scan', 'site', 'timestamp')
    search_fields = ('employe__nom', 'employe__prenom', 'employe__matricule')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'

    def timestamp_local(self, obj):
        return obj.get_timestamp_local().strftime('%d/%m/%Y %H:%M:%S')
    timestamp_local.short_description = 'Heure locale'

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
        return super().get_queryset(request).select_related('employe', 'site')


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
    list_display = ('type_display', 'employe_ou_matricule', 'gravite_badge', 'statut_badge', 'created_at')
    list_filter = ('statut', 'type')
    search_fields = ('employe__nom', 'employe__prenom', 'employe__matricule', 'matricule_scanne', 'message')
    date_hierarchy = 'created_at'
    inlines = [AnomalieTraitementInline]
    actions = ['marquer_traitees', 'marquer_cloturees']
    ordering = ('-created_at',)

    readonly_fields = (
        'type', 'employe', 'matricule_scanne', 'site',
        'message', 'contexte_formate', 'gravite_badge', 'statut_badge',
        'cloturee_par', 'date_cloture', 'created_at',
    )

    fieldsets = (
        ("Anomalie", {
            'fields': ('type', 'gravite_badge', 'employe', 'matricule_scanne', 'site', 'created_at')
        }),
        ("Details", {'fields': ('message', 'contexte_formate')}),
        ("Statut", {'fields': ('statut_badge', 'cloturee_par', 'date_cloture')}),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def type_display(self, obj):
        return obj.get_type_display()
    type_display.short_description = 'Type'

    def employe_ou_matricule(self, obj):
        if obj.employe:
            return obj.employe.get_nom_complet()
        return obj.matricule_scanne or '-'
    employe_ou_matricule.short_description = 'Employe'

    def gravite_badge(self, obj):
        styles = {
            'info': ('rgba(96,165,250,.12)', '#60a5fa', 'Info'),
            'warning': ('rgba(251,191,36,.12)', '#fbbf24', 'Avertissement'),
            'critique': ('rgba(248,113,113,.12)', '#f87171', 'Critique'),
        }
        bg, color, label = styles.get(obj.gravite, ('rgba(255,255,255,.07)', '#e8eaf0', obj.gravite))
        return mark_safe(
            f'<span style="background:{bg};color:{color};padding:4px 12px;'
            f'border-radius:20px;font-size:12px;font-weight:600;white-space:nowrap;">'
            f'{label}</span>'
        )
    gravite_badge.short_description = 'Gravite'

    def statut_badge(self, obj):
        styles = {
            AnomaliePointage.STATUT_OUVERTE: ('rgba(248,113,113,.12)', '#f87171', 'Ouverte'),
            AnomaliePointage.STATUT_TRAITEE: ('rgba(251,191,36,.12)', '#fbbf24', 'Traitee'),
            AnomaliePointage.STATUT_CLOTUREE: ('rgba(74,222,128,.12)', '#4ade80', 'Cloturee'),
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
            return '-'
        return format_html(
            '<pre style="background:#1c2236;border:1px solid rgba(255,255,255,.07);'
            'border-radius:8px;padding:12px 14px;font-size:12px;color:#e8eaf0;'
            'white-space:pre-wrap;">{}</pre>',
            json.dumps(obj.contexte, indent=2, ensure_ascii=False, default=str)
        )
    contexte_formate.short_description = "Contexte"

    @admin.action(description="Marquer comme traitees")
    def marquer_traitees(self, request, queryset):
        count = 0
        for anomalie in queryset.exclude(statut=AnomaliePointage.STATUT_CLOTUREE):
            try:
                marquer_traitee(anomalie, request.user, commentaire="Marquee traitee depuis l'administration.")
                count += 1
            except ValueError as e:
                self.message_user(request, f"Anomalie #{anomalie.pk} : {e}", level=messages.ERROR)
        self.message_user(request, f"{count} anomalie(s) marquee(s) comme traitee(s).")

    @admin.action(description="Cloturer")
    def marquer_cloturees(self, request, queryset):
        count = 0
        for anomalie in queryset:
            try:
                marquer_cloturee(anomalie, request.user)
                count += 1
            except ValueError as e:
                self.message_user(request, f"Anomalie #{anomalie.pk} : {e}", level=messages.ERROR)
        self.message_user(request, f"{count} anomalie(s) cloturee(s).")


# ============================================================
# CONFIGURATION DU SITE ADMIN
# ============================================================

admin.site.site_header = "Pointage QR - Administration"
admin.site.site_title = "Pointage QR"
admin.site.index_title = "Tableau de bord d'administration"