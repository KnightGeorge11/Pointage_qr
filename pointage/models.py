# pointage/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import qrcode
from io import BytesIO
from django.core.files import File
from PIL import Image, ImageDraw
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
    sites           = models.ManyToManyField(Site, related_name='employes')
    qr_code         = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    qr_code_token   = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    date_creation   = models.DateTimeField(auto_now_add=True)
    actif           = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.matricule})"

    def save(self, *args, **kwargs):
        if not self.qr_code:
            self.generer_qr_code()
        super().save(*args, **kwargs)

    def generer_qr_code(self):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        # Format : EMPLOYE:matricule:uuid_token
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

    employe          = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name='pointages')
    site             = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='pointages')
    date_pointage    = models.DateField()
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

            # Pour l'après-midi : soustraire la durée de pause autorisée
            # (intervalle entre fermeture matin et ouverture après-midi du site)
            # afin de ne pas comptabiliser la pause comme du retard.
            # Exemple : ouverture AM = 13h30, fermeture matin = 12h00
            # → pause = 1h30. Si l'employé arrive à 13h45, retard réel = 15 min.
            if self.periode == 'apres_midi':
                _, fermeture_matin = self.site.get_horaires_pour_periode('matin')
                if fermeture_matin:
                    pause_duree = datetime.combine(
                        self.date_pointage, heure_ouverture
                    ) - datetime.combine(
                        self.date_pointage, fermeture_matin
                    )
                    # Sécurité : ne soustraire que si la pause est positive
                    if pause_duree > timedelta(0):
                        retard_brut = retard_brut  # déjà calculé depuis ouverture AM

            self.retard = max(retard_brut, timedelta(0))
        else:
            self.retard = timedelta(0)

    def calculer_heures_travaillees(self):
        if not self.heure_arrivee:
            self.heures_travaillees = timedelta(0)
            return

        if self.periode == 'nuit':
            if self.heure_depart:
                debut = datetime.combine(self.date_pointage, self.heure_arrivee)
                fin   = datetime.combine(self.date_pointage, self.heure_depart)
                tz    = timezone.get_current_timezone()
                debut = timezone.make_aware(debut, tz)
                fin   = timezone.make_aware(fin, tz)
                if fin < debut:
                    fin += timedelta(days=1)
                self.heures_travaillees = fin - debut
            else:
                maintenant = timezone.localtime(timezone.now())
                debut      = datetime.combine(self.date_pointage, self.heure_arrivee)
                debut      = timezone.make_aware(debut, timezone.get_current_timezone())
                self.heures_travaillees = maintenant - debut
        else:
            if self.heure_arrivee and self.heure_depart:
                tz     = timezone.get_current_timezone()
                arrivee = timezone.make_aware(datetime.combine(self.date_pointage, self.heure_arrivee), tz)
                depart  = timezone.make_aware(datetime.combine(self.date_pointage, self.heure_depart),  tz)
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

    employe   = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name='scans')
    site      = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='scans')
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


# ─── NOUVEAU : Modèle AlerteRH ────────────────────────────────────────────────

class AlerteRH(models.Model):
    TYPE_ALERTE = [
        ('QR_INVALIDE',          'QR code invalide'),
        ('SITE_NON_AUTORISE',    'Site non autorisé'),
        ('HORS_PLAGE',           'Scan hors plage horaire'),
        ('SCAN_EXCESS',          'Scan excédentaire (> 4/jour)'),
        ('SCAN_MANQUANT',        'Scan(s) manquant(s) en fin de journée'),
        ('DOUBLON',              'Scan dupliqué'),
        ('SORTIE_ANTICIPEE',     'Sortie anticipée autorisée'),
        ('SORTIE_NON_AUTORISEE', 'Sortie anticipée non autorisée'),
    ]

    employe    = models.ForeignKey(
        Employe, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='alertes'
    )
    type       = models.CharField(max_length=30, choices=TYPE_ALERTE, db_index=True)
    detail     = models.TextField(blank=True)
    timestamp  = models.DateTimeField()
    traitee    = models.BooleanField(default=False)
    traitee_par = models.ForeignKey(
        'CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='alertes_traitees'
    )
    date_traitement = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        emp = self.employe.get_nom_complet() if self.employe else "Inconnu"
        return f"[{self.get_type_display()}] {emp} — {self.timestamp.strftime('%d/%m/%Y %H:%M')}"

    class Meta:
        ordering        = ['-timestamp']
        verbose_name    = "Alerte RH"
        verbose_name_plural = "Alertes RH"
        indexes = [
            models.Index(fields=['type', 'timestamp']),
            models.Index(fields=['traitee', 'timestamp']),
            models.Index(fields=['employe', 'timestamp']),
        ]


class AutorisationSortie(models.Model):
    """
    Quota mensuel de sortie anticipée par employé.
    Chaque employé dispose d'une autorisation d'1h maximum par mois.
    Une seule utilisation autorisée par mois (fractionnement non autorisé).

    Cycle de vie :
      - Créé automatiquement lors de la première demande du mois
        (ou pré-créé par un admin pour le mois en cours)
      - utilisee = False  → disponible
      - utilisee = True   → épuisée pour ce mois
    """

    employe         = models.ForeignKey(
        Employe, on_delete=models.CASCADE, related_name='autorisations_sortie'
    )
    mois            = models.PositiveSmallIntegerField()   # 1-12
    annee           = models.PositiveSmallIntegerField()
    utilisee        = models.BooleanField(default=False)
    date_utilisation = models.DateTimeField(null=True, blank=True)
    # Heure de départ réelle (heure de scan de sortie anticipée)
    heure_depart_reel = models.TimeField(null=True, blank=True)
    # Pointage concerné par la sortie anticipée
    pointage        = models.ForeignKey(
        Pointage, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='autorisation_sortie'
    )
    # Agent qui a confirmé (réceptionniste / agent de sécurité)
    confirme_par    = models.ForeignKey(
        'CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='autorisations_confirmees'
    )
    note            = models.TextField(blank=True)

    class Meta:
        unique_together     = ('employe', 'mois', 'annee')
        ordering            = ['-annee', '-mois']
        verbose_name        = "Autorisation de sortie anticipée"
        verbose_name_plural = "Autorisations de sortie anticipée"
        indexes = [
            models.Index(fields=['employe', 'annee', 'mois']),
        ]

    def __str__(self):
        statut = "utilisée" if self.utilisee else "disponible"
        return (
            f"{self.employe.get_nom_complet()} — "
            f"{self.mois:02d}/{self.annee} [{statut}]"
        )

    @classmethod
    def get_ou_creer_du_mois(cls, employe, date):
        """
        Retourne l'autorisation du mois pour cet employé,
        en la créant si elle n'existe pas encore.
        """
        obj, _ = cls.objects.get_or_create(
            employe=employe,
            mois=date.month,
            annee=date.year,
        )
        return obj

    @property
    def disponible(self):
        return not self.utilisee


class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Administrateur'),
        ('user',  'Utilisateur'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')

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