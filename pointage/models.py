from django.db import models
import qrcode
from io import BytesIO
from django.core.files import File
import uuid
from datetime import timedelta, datetime, time
from django.utils import timezone
from typing import Optional
from django.contrib.auth.models import AbstractUser


class Poste(models.Model):
    nom         = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    couleur     = models.CharField(max_length=20, default='#4361ee')

    def __str__(self):
        return self.nom

    class Meta:
        ordering        = ['nom']
        verbose_name    = "Poste"
        verbose_name_plural = "Postes"


class Site(models.Model):
    nom                       = models.CharField(max_length=100)
    adresse                   = models.TextField()
    heure_ouverture_matin     = models.TimeField(default='08:00')
    heure_fermeture_matin     = models.TimeField(default='12:00')
    heure_ouverture_apres_midi = models.TimeField(default='13:30')
    heure_fermeture_apres_midi = models.TimeField(default='17:30')

    def __str__(self):
        return f"{self.nom} - {self.adresse[:30]}..."

    def get_horaires_pour_periode(self, periode: str) -> tuple:
        if periode == 'matin':
            return self.heure_ouverture_matin, self.heure_fermeture_matin
        elif periode == 'apres_midi':
            return self.heure_ouverture_apres_midi, self.heure_fermeture_apres_midi
        return None, None

    class Meta:
        ordering        = ['nom']
        verbose_name    = "Site"
        verbose_name_plural = "Sites"


class Employe(models.Model):
    poste           = models.ForeignKey(Poste, on_delete=models.SET_NULL, null=True, blank=True, related_name='employes')
    nom             = models.CharField(max_length=100)
    prenom          = models.CharField(max_length=100)
    matricule       = models.CharField(max_length=50, unique=True)
    qr_code         = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    qr_code_token   = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    date_creation   = models.DateTimeField(auto_now_add=True)
    actif           = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.matricule})"

    def save(self, *args, **kwargs):
        # Régénérer le QR à la création, ET si le matricule a changé —
        # sinon le badge physique garde l'ancien matricule encodé et
        # cesse silencieusement de fonctionner après un renommage
        # (Point 8 — cohérence matricule/QR).
        matricule_a_change = False
        if self.pk:
            ancien_matricule = Employe.objects.filter(pk=self.pk).values_list('matricule', flat=True).first()
            if ancien_matricule is not None and ancien_matricule != self.matricule:
                matricule_a_change = True

        if not self.qr_code or matricule_a_change:
            self.generer_qr_code()
        super().save(*args, **kwargs)

    def generer_qr_code(self):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        data = f"EMPLOYE:{self.matricule}:{self.qr_code_token}"
        qr.add_data(data)
        qr.make(fit=True)
        img      = qr.make_image(fill_color="black", back_color="white")
        buffer   = BytesIO()
        img.save(buffer, format='PNG')
        filename = f'qr_code_{self.matricule}.png'
        self.qr_code.save(filename, File(buffer), save=False)

    def get_nom_complet(self) -> str:
        return f"{self.prenom} {self.nom}"

    def est_present_aujourdhui(self) -> bool:
        today = timezone.localtime(timezone.now()).date()
        return self.pointages.filter(date_pointage=today).exists()

    def get_pointages_du_jour(self, date: Optional[datetime.date] = None):
        if date is None:
            date = timezone.localtime(timezone.now()).date()
        return self.pointages.filter(date_pointage=date).select_related('site')

    def get_statut_journee(self, date: Optional[datetime.date] = None) -> dict:
        if date is None:
            date = timezone.localtime(timezone.now()).date()

        statut = {
            'date': date,
            'employe': {
                'id':          self.id,
                'nom_complet': self.get_nom_complet(),
                'matricule':   self.matricule,
                'poste':       self.poste.nom if self.poste else None,
            },
            'matin':      {'present': False, 'heure_arrivee': None, 'heure_depart': None, 'site': None},
            'apres_midi': {'present': False, 'heure_arrivee': None, 'heure_depart': None, 'site': None},
            'nuit':       {'present': False, 'heure_arrivee': None, 'heure_depart': None, 'site': None, 'type_journee': None},
        }

        for pointage in self.get_pointages_du_jour(date):
            if pointage.periode == 'matin':
                statut['matin'].update({
                    'present': True,
                    'heure_arrivee': pointage.heure_arrivee,
                    'heure_depart':  pointage.heure_depart,
                    'site':          pointage.site.nom if pointage.site else None,
                })
            elif pointage.periode == 'apres_midi':
                statut['apres_midi'].update({
                    'present': True,
                    'heure_arrivee': pointage.heure_arrivee,
                    'heure_depart':  pointage.heure_depart,
                    'site':          pointage.site.nom if pointage.site else None,
                })
            elif pointage.periode == 'nuit':
                statut['nuit'].update({
                    'present':       True,
                    'heure_arrivee': pointage.heure_arrivee,
                    'heure_depart':  pointage.heure_depart,
                    'site':          pointage.site.nom if pointage.site else None,
                    'type_journee':  pointage.type_journee,
                })

        return statut

    def get_heures_travaillees_jour(self, date: Optional[datetime.date] = None) -> timedelta:
        if date is None:
            date = timezone.localtime(timezone.now()).date()
        total = timedelta()
        for pointage in self.get_pointages_du_jour(date):
            if pointage.heures_travaillees:
                total += pointage.heures_travaillees
        return total

    class Meta:
        ordering        = ['nom', 'prenom']
        verbose_name    = "Employé"
        verbose_name_plural = "Employés"
        indexes = [
            models.Index(fields=['matricule', 'actif']),
        ]


class Pointage(models.Model):
    PERIODE_CHOICES = [
        ('matin',      'Matin'),
        ('apres_midi', 'Après-midi'),
        ('nuit',       'Nuit'),
    ]

    TYPE_JOURNEE_CHOICES = [
        ('normal', 'Journée normale'),
        ('garde',  'Garde de nuit'),
    ]

    STATUT_CHOICES = [
        ('present', 'Présent'),
        ('absent',  'Absent'),
        ('retard',  'En retard'),
        ('congé',   'Congé'),
        ('maladie', 'Maladie'),
    ]

    employe          = models.ForeignKey(Employe, on_delete=models.PROTECT, related_name='pointages')
    site             = models.ForeignKey(Site, on_delete=models.PROTECT, related_name='pointages')
    date_pointage    = models.DateField()
    date_depart      = models.DateField(null=True, blank=True)  # ✅ NOUVEAU : date réelle de fin pour les gardes
    periode          = models.CharField(max_length=20, choices=PERIODE_CHOICES)
    type_journee     = models.CharField(max_length=20, choices=TYPE_JOURNEE_CHOICES, default='normal', db_index=True)

    heure_arrivee    = models.TimeField(null=True, blank=True)
    heure_depart     = models.TimeField(null=True, blank=True)
    retard           = models.DurationField(null=True, blank=True)
    heures_travaillees = models.DurationField(null=True, blank=True)

    statut           = models.CharField(max_length=20, choices=STATUT_CHOICES, default='present')
    notes            = models.TextField(blank=True)
    date_creation    = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    def __str__(self):
        site_nom = self.site.nom if self.site else "Aucun site"
        return f"{self.employe} - {self.date_pointage} ({self.get_periode_display()}) - {site_nom}"

    def get_display_name(self) -> str:
        return f"Pointage {self.employe.get_nom_complet()} - {self.date_pointage.strftime('%d/%m/%Y')} ({self.periode})"

    def get_duree_formatee(self) -> str:
        """Retourne la durée formatée en 'Xj XhXX' ou 'XhXX'"""
        if not self.heures_travaillees:
            return "0h00"
        total_secondes = int(self.heures_travaillees.total_seconds())
        jours = total_secondes // 86400
        heures = (total_secondes % 86400) // 3600
        minutes = (total_secondes % 3600) // 60
        
        if jours > 0:
            return f"{jours}j {heures}h{minutes:02d}"
        return f"{heures}h{minutes:02d}"

    def calculer_retard(self):
        if self.periode == 'nuit':
            self.retard = timedelta(0)
            return

        if not self.heure_arrivee or not self.site:
            self.retard = None
            return

        heure_ouverture, _ = self.site.get_horaires_pour_periode(self.periode)

        if heure_ouverture:
            arrivee_dt   = datetime.combine(self.date_pointage, self.heure_arrivee)
            ouverture_dt = datetime.combine(self.date_pointage, heure_ouverture)
            retard_brut  = arrivee_dt - ouverture_dt

            if self.periode == 'apres_midi':
                _, fermeture_matin = self.site.get_horaires_pour_periode('matin')
                if fermeture_matin:
                    pause_duree = datetime.combine(
                        self.date_pointage, heure_ouverture
                    ) - datetime.combine(
                        self.date_pointage, fermeture_matin
                    )
                    if pause_duree > timedelta(0):
                        retard_brut = retard_brut

            self.retard = max(retard_brut, timedelta(0))
        else:
            self.retard = timedelta(0)

    def calculer_heures_travaillees(self):
        """Calcule les heures travaillées en gérant correctement les gardes de nuit qui chevauchent minuit"""
        if not self.heure_arrivee:
            self.heures_travaillees = timedelta(0)
            return

        tz = timezone.get_current_timezone()
        
        if self.periode == 'nuit':
            # GARDE DE NUIT
            if self.heure_depart:
                # Date d'arrivée = date_pointage
                date_arrivee = self.date_pointage
                
                # Date de départ = date_depart si renseignée, sinon date_pointage
                if self.date_depart:
                    date_depart = self.date_depart
                else:
                    # Fallback : si heure_depart < heure_arrivee, c'est le lendemain
                    date_depart = self.date_pointage
                    if self.heure_depart < self.heure_arrivee:
                        date_depart += timedelta(days=1)
                
                arrivee = timezone.make_aware(
                    datetime.combine(date_arrivee, self.heure_arrivee),
                    tz
                )
                depart = timezone.make_aware(
                    datetime.combine(date_depart, self.heure_depart),
                    tz
                )
                
                self.heures_travaillees = depart - arrivee
            else:
                # Pas encore terminé → on calcule jusqu'à maintenant
                maintenant = timezone.localtime(timezone.now())
                arrivee = timezone.make_aware(
                    datetime.combine(self.date_pointage, self.heure_arrivee),
                    tz
                )
                self.heures_travaillees = maintenant - arrivee
                
        else:
            # PÉRIODE NORMALE (matin / après-midi)
            if self.heure_arrivee and self.heure_depart:
                arrivee = timezone.make_aware(
                    datetime.combine(self.date_pointage, self.heure_arrivee),
                    tz
                )
                depart = timezone.make_aware(
                    datetime.combine(self.date_pointage, self.heure_depart),
                    tz
                )
                if depart < arrivee:
                    depart += timedelta(days=1)
                self.heures_travaillees = depart - arrivee
            else:
                self.heures_travaillees = timedelta(0)

    def save(self, *args, **kwargs):
        if self.periode != 'nuit':
            self.calculer_retard()
        self.calculer_heures_travaillees()

        if self.periode == 'nuit':
            self.statut = 'present' if self.heure_arrivee else 'absent'
        else:
            if not self.heure_arrivee:
                if self.statut == 'present':
                    self.statut = 'absent'
            elif self.retard and self.retard.total_seconds() > 300:
                self.statut = 'retard'
            else:
                self.statut = 'present'

        super().save(*args, **kwargs)

    def enregistrer_entree(self, heure_arrivee: time, site: Site = None):
        self.heure_arrivee = heure_arrivee
        if site:
            self.site = site
        self.save()

    def enregistrer_sortie(self, heure_depart: time):
        self.heure_depart = heure_depart
        self.save()

    def est_complet(self) -> bool:
        return bool(self.heure_arrivee and self.heure_depart)

    def get_retard_minutes(self) -> int:
        if self.periode == 'nuit':
            return 0
        return int(self.retard.total_seconds() // 60) if self.retard else 0

    class Meta:
        unique_together = ['employe', 'date_pointage', 'periode']
        ordering        = ['-date_pointage', 'periode', 'employe']
        verbose_name    = "Pointage"
        verbose_name_plural = "Pointages"
        indexes = [
            models.Index(fields=['date_pointage']),
            models.Index(fields=['employe', 'date_pointage']),
            models.Index(fields=['statut', 'date_pointage']),
            models.Index(fields=['site', 'date_pointage']),
            models.Index(fields=['type_journee']),
            models.Index(fields=['employe', 'periode', 'type_journee', 'heure_depart']),
            models.Index(fields=['date_pointage', 'periode', 'retard']),
            models.Index(fields=['date_pointage', 'heure_arrivee']),
            models.Index(fields=['date_pointage', 'heure_depart']),
        ]


class Scan(models.Model):
    TYPE_SCAN = [
        ('entree_matin',       'Entrée matin'),
        ('sortie_matin',       'Sortie matin'),
        ('entree_apres_midi',  'Entrée après-midi'),
        ('sortie_apres_midi',  'Sortie après-midi'),
        ('debut_garde',        'Début garde (nuit)'),
        ('fin_garde',          'Fin garde (nuit)'),
    ]

    employe   = models.ForeignKey(Employe, on_delete=models.PROTECT, related_name='scans')
    site      = models.ForeignKey(Site, on_delete=models.PROTECT, related_name='scans')
    timestamp = models.DateTimeField()
    type_scan = models.CharField(max_length=20, choices=TYPE_SCAN, null=True, blank=True)
    pointage  = models.ForeignKey(Pointage, on_delete=models.SET_NULL, null=True, blank=True, related_name='scans')
    actif     = models.BooleanField(default=True)

    def __str__(self):
        return f"Scan {self.employe} - {self.get_type_scan_display()} - {self.get_timestamp_local().strftime('%H:%M')}"

    def get_timestamp_local(self) -> datetime:
        return timezone.localtime(self.timestamp)

    def get_type_scan_display(self):
        return dict(self.TYPE_SCAN).get(self.type_scan, self.type_scan or "Inconnu")

    def get_details(self) -> dict:
        return {
            'id':                  self.id,
            'employe': {
                'id':          self.employe.id,
                'nom_complet': self.employe.get_nom_complet(),
                'matricule':   self.employe.matricule,
            },
            'site':              self.site.nom if self.site else None,
            'type_scan':         self.type_scan,
            'type_scan_display': self.get_type_scan_display(),
            'timestamp':         self.timestamp.isoformat(),
            'timestamp_local':   self.get_timestamp_local().isoformat(),
            'pointage_id':       self.pointage.id if self.pointage else None,
            'actif':             self.actif,
        }

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Scan"
        verbose_name_plural = "Scans"
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['employe', 'timestamp']),
            models.Index(fields=['type_scan', 'timestamp']),
        ]


class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Administrateur'),
        ('user',  'Utilisateur'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')

    # === AJOUT : Définition explicite des relations groups et user_permissions ===
    # Ces deux lignes sont ajoutées pour résoudre le problème de la table manquante
    # "pointage_customuser_user_permissions". Elles sont nécessaires pour que Django
    # crée correctement les tables de liaison many-to-many.
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='customuser_set',
        blank=True,
        verbose_name='groups',
        help_text='The groups this user belongs to.'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='customuser_set',
        blank=True,
        verbose_name='user permissions',
        help_text='Specific permissions for this user.'
    )

    def save(self, *args, **kwargs):
        self.is_staff = (self.role == 'admin') or self.is_superuser
        super().save(*args, **kwargs)

    class Meta:
        verbose_name        = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'


class DemandeModification(models.Model):
    TYPE_CHOICES = (
        ('create', 'Création'),
        ('update', 'Modification'),
        ('delete', 'Suppression'),
    )
    CIBLE_CHOICES = (
        ('employe', 'Employé'),
        ('site',    'Site'),
        ('poste',   'Poste'),
    )
    STATUT_CHOICES = (
        ('en_attente', 'En attente'),
        ('approuvee',  'Approuvée'),
        ('refusee',    'Refusée'),
    )

    demandeur       = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='demandes')
    type_action     = models.CharField(max_length=10,  choices=TYPE_CHOICES)
    cible           = models.CharField(max_length=20,  choices=CIBLE_CHOICES)
    cible_id        = models.IntegerField(null=True, blank=True)
    donnees         = models.JSONField(default=dict)
    statut          = models.CharField(max_length=20,  choices=STATUT_CHOICES, default='en_attente')
    commentaire     = models.TextField(blank=True)
    date_creation   = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(null=True, blank=True)
    traitee_par     = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='demandes_traitees'
    )

    def __str__(self):
        return f"{self.get_type_action_display()} {self.get_cible_display()} — {self.demandeur} ({self.get_statut_display()})"

    class Meta:
        ordering        = ['-date_creation']
        verbose_name    = "Demande de modification"
        verbose_name_plural = "Demandes de modification"


# ============================================================
# GESTION DES ANOMALIES DE POINTAGE (Phase 4)
# ============================================================
#
# Couche de persistance et de traçabilité posée AU-DESSUS du moteur
# métier (domain.py / state_machine.py / context.py / services.py),
# sans jamais le modifier :
#
#   - "type" reprend, pour les anomalies venant d'une ScanDecision
#     refusée, exactement la valeur de domain.AnomalyCode.value
#     (ex: 'during_break', 'missing_morning_exit'...) ;
#   - trois types supplémentaires (invalid_qr et duplicate_scan mis à
#     part, déjà présents dans AnomalyCode) couvrent les refus détectés
#     en amont de la machine à états, dans process_scan() : QR invalide,
#     employé inactif, site invalide, hors plage horaire globale.
#
# Cette couche ne décide jamais rien : elle enregistre, après coup, ce
# que le moteur métier a déjà décidé.

class AnomaliePointage(models.Model):
    """Anomalie détectée lors d'un scan (refus, cas limite, échec de
    validation), conservée pour suivi et traitement administratif.
    """

    # Types issus de domain.AnomalyCode (mêmes valeurs, pour rester alignés
    # avec la couche métier sans avoir à la modifier ni à la réimporter ici)
    TYPE_INVALID_QR             = 'invalid_qr'
    TYPE_DUPLICATE_SCAN         = 'duplicate_scan'
    TYPE_OUTSIDE_HOURS          = 'outside_hours'
    TYPE_DURING_BREAK           = 'during_break'
    TYPE_DAY_COMPLETE           = 'day_complete'
    TYPE_MISSING_MORNING_EXIT   = 'missing_morning_exit'
    TYPE_TRANSITION_IMPOSSIBLE  = 'transition_impossible'
    TYPE_INVALID_STATE          = 'invalid_state'
    # Types propres aux pré-contrôles de process_scan() (n'existent pas
    # dans AnomalyCode, qui ne concerne que les décisions de la machine
    # à états) :
    TYPE_EMPLOYE_INACTIF        = 'employe_inactif'
    TYPE_SITE_INVALIDE          = 'site_invalide'
    TYPE_HORS_PLAGE_GLOBALE     = 'hors_plage_globale'
    TYPE_GARDE_MULTIPLE_NON_SUPPORTEE = 'garde_multiple_non_supportee'

    TYPE_CHOICES = (
        (TYPE_INVALID_QR,            'QR invalide'),
        (TYPE_EMPLOYE_INACTIF,       'Employé inactif'),
        (TYPE_SITE_INVALIDE,         'Site invalide'),
        (TYPE_HORS_PLAGE_GLOBALE,    'Hors plage horaire globale'),
        (TYPE_DUPLICATE_SCAN,        'Double scan'),
        (TYPE_OUTSIDE_HOURS,         'Hors horaires du site'),
        (TYPE_DURING_BREAK,          'Scan pendant la pause'),
        (TYPE_DAY_COMPLETE,          'Journée déjà terminée'),
        (TYPE_MISSING_MORNING_EXIT,  'Sortie matin manquante'),
        (TYPE_TRANSITION_IMPOSSIBLE, 'Transition impossible'),
        (TYPE_INVALID_STATE,         'État invalide'),
        (TYPE_GARDE_MULTIPLE_NON_SUPPORTEE, 'Deuxième garde le même jour non prise en charge'),
    )

    # Gravité dérivée du type — jamais stockée, toujours recalculée.
    GRAVITE_PAR_TYPE = {
        TYPE_INVALID_QR:            'critique',
        TYPE_EMPLOYE_INACTIF:       'critique',
        TYPE_SITE_INVALIDE:         'critique',
        TYPE_INVALID_STATE:         'critique',
        TYPE_HORS_PLAGE_GLOBALE:    'warning',
        TYPE_OUTSIDE_HOURS:         'warning',
        TYPE_DURING_BREAK:          'warning',
        TYPE_MISSING_MORNING_EXIT:  'warning',
        TYPE_TRANSITION_IMPOSSIBLE: 'warning',
        TYPE_GARDE_MULTIPLE_NON_SUPPORTEE: 'warning',
        TYPE_DAY_COMPLETE:          'info',
        TYPE_DUPLICATE_SCAN:        'info',
    }
    GRAVITE_CHOICES = (
        ('info',     'Info'),
        ('warning',  'Avertissement'),
        ('critique', 'Critique'),
    )

    STATUT_OUVERTE  = 'ouverte'
    STATUT_TRAITEE  = 'traitee'
    STATUT_CLOTUREE = 'cloturee'
    STATUT_CHOICES = (
        (STATUT_OUVERTE,  'Ouverte'),
        (STATUT_TRAITEE,  'Traitée'),
        (STATUT_CLOTUREE, 'Clôturée'),
    )

    type             = models.CharField(max_length=30, choices=TYPE_CHOICES)
    employe          = models.ForeignKey(
        Employe, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='anomalies'
    )
    matricule_scanne = models.CharField(
        max_length=50, blank=True,
        help_text="Matricule brut du QR scanné, conservé même si l'employé "
                   "n'a pas pu être identifié (ex: QR invalide)."
    )
    site             = models.ForeignKey(
        Site, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='anomalies'
    )
    date_pointage    = models.DateField(null=True, blank=True)
    message          = models.TextField()
    contexte         = models.JSONField(default=dict, blank=True)
    statut           = models.CharField(
        max_length=10, choices=STATUT_CHOICES, default=STATUT_OUVERTE
    )
    cloturee_par     = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='anomalies_cloturees', db_constraint=False
    )
    date_cloture     = models.DateTimeField(null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        qui = self.employe.get_nom_complet() if self.employe else (self.matricule_scanne or '?')
        return f"{self.get_type_display()} — {qui} ({self.get_statut_display()})"

    @property
    def gravite(self) -> str:
        """Gravité dérivée du type — jamais persistée."""
        return self.GRAVITE_PAR_TYPE.get(self.type, 'info')

    def get_gravite_display(self) -> str:
        return dict(self.GRAVITE_CHOICES).get(self.gravite, self.gravite)

    class Meta:
        ordering        = ['-created_at']
        verbose_name    = "Anomalie de pointage"
        verbose_name_plural = "Anomalies de pointage"
        indexes = [
            models.Index(fields=['statut', 'created_at']),
            models.Index(fields=['type', 'created_at']),
            models.Index(fields=['employe', 'date_pointage']),
        ]


class AnomalieTraitement(models.Model):
    """Trace de traitement d'une anomalie : qui, quand, pourquoi, et — le
    cas échéant — quelles valeurs de pointage ont été corrigées.

    Une anomalie n'a qu'un seul traitement (OneToOne) : si elle doit être
    retraitée, elle repasse par le service dédié qui met à jour cet
    enregistrement plutôt que d'en créer un second, pour garder un
    historique simple et non ambigu.
    """
    # ================================================================
    # ACTION — l'action de traitement effectuée sur l'anomalie.
    # À NE PAS CONFONDRE avec AnomaliePointage.statut (ouverte/traitee/
    # cloturee), qui décrit l'état de l'anomalie. Ici on décrit QUELLE
    # action RH a été posée. La clôture n'est PAS une valeur de ce champ :
    # elle est gérée séparément par marquer_cloturee() sur AnomaliePointage
    # (cloturee_par/date_cloture) et ne modifie jamais le type_action du
    # dernier traitement réel (correction/justification/rejet).
    # ================================================================
    ACTION_CORRECTION    = 'correction'
    ACTION_JUSTIFICATION = 'justification'
    ACTION_REJET          = 'rejet'
    TYPE_ACTION_CHOICES = [
        (ACTION_CORRECTION,    'Correction du pointage'),
        (ACTION_JUSTIFICATION, 'Justification'),
        (ACTION_REJET,         'Rejet'),
    ]
    type_action = models.CharField(
        max_length=20,
        choices=TYPE_ACTION_CHOICES,
        default=ACTION_CORRECTION,
        verbose_name="Type d'action"
    )
    # ================================================================
    anomalie        = models.OneToOneField(
        AnomaliePointage, on_delete=models.CASCADE, related_name='traitement'
    )
    administrateur  = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='anomalies_traitees', db_constraint=False
    )
    # auto_now (pas auto_now_add) : cet enregistrement est mis à jour en
    # place si l'anomalie est retraitée (cf. docstring de la classe) —
    # la date doit donc refléter le DERNIER traitement, pas le premier.
    date_traitement = models.DateTimeField(auto_now=True)
    commentaire     = models.TextField(blank=True)
    pointage_concerne = models.ForeignKey(
        Pointage, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='corrections_anomalies'
    )
    # Liste de corrections effectuées, le cas échéant :
    # [{'champ': 'heure_arrivee', 'ancienne_valeur': '08:15', 'nouvelle_valeur': '08:00'}, ...]
    corrections     = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"Traitement de {self.anomalie} par {self.administrateur or '—'}"

    class Meta:
        ordering        = ['-date_traitement']
        verbose_name    = "Traitement d'anomalie"
        verbose_name_plural = "Traitements d'anomalies"