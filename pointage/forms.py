from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import Employe, Site, Pointage, CustomUser, ConfigurationPointage


class CustomUserCreationForm(UserCreationForm):
    """Création d'un compte CustomUser avec hashage Django du mot de passe."""
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active')


class CustomUserChangeForm(UserChangeForm):
    """Modification d'un CustomUser compatible avec le modèle réel du projet."""
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'password')


class EmployeForm(forms.ModelForm):
    class Meta:
        model = Employe
        fields = ['poste', 'nom', 'prenom', 'matricule', 'email', 'telephone', 'actif']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control'}),
            'matricule': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'poste': forms.Select(attrs={'class': 'form-control'}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'poste': 'Poste',
            'nom': 'Nom',
            'prenom': 'Prénom',
            'matricule': 'Matricule',
            'email': 'E-mail',
            'telephone': 'Téléphone',
            'actif': 'Actif',
        }

class SiteForm(forms.ModelForm):
    class Meta:
        model = Site
        fields = ['nom', 'adresse', 'heure_ouverture_matin', 'heure_fermeture_matin',
                 'heure_ouverture_apres_midi', 'heure_fermeture_apres_midi',
                 'tolerance_minutes', 'seuil_depart_anticipe_minutes']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'heure_ouverture_matin': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heure_fermeture_matin': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heure_ouverture_apres_midi': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heure_fermeture_apres_midi': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'tolerance_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'seuil_depart_anticipe_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }
        labels = {
            'nom': 'Nom du site',
            'adresse': 'Adresse',
            'heure_ouverture_matin': "Heure d'ouverture (matin)",
            'heure_fermeture_matin': 'Heure de fermeture (matin)',
            'heure_ouverture_apres_midi': "Heure d'ouverture (après-midi)",
            'heure_fermeture_apres_midi': 'Heure de fermeture (après-midi)',
        }


class ConfigurationPointageForm(forms.ModelForm):
    """Formulaire Jazzmin clair pour les horaires globaux du pointage."""
    class Meta:
        model = ConfigurationPointage
        fields = [
            'heure_debut_systeme',
            'heure_fin_systeme',
            'heure_bascule_apres_midi',
            'heure_debut_garde',
            'heure_fin_garde',
            'tolerance_minutes_defaut',
            'seuil_depart_anticipe_minutes_defaut',
            'duree_journee_reference',
        ]
        widgets = {
            'heure_debut_systeme': forms.TimeInput(
                attrs={'type': 'time', 'step': 60}
            ),
            'heure_fin_systeme': forms.TimeInput(
                attrs={'type': 'time', 'step': 60}
            ),
            'heure_bascule_apres_midi': forms.TimeInput(
                attrs={'type': 'time', 'step': 60}
            ),
            'heure_debut_garde': forms.TimeInput(
                attrs={'type': 'time', 'step': 60}
            ),
            'heure_fin_garde': forms.TimeInput(
                attrs={'type': 'time', 'step': 60}
            ),
            'tolerance_minutes_defaut': forms.NumberInput(
                attrs={'min': 0, 'step': 1}
            ),
            'seuil_depart_anticipe_minutes_defaut': forms.NumberInput(
                attrs={'min': 0, 'step': 1}
            ),
            'duree_journee_reference': forms.TextInput(
                attrs={
                    'placeholder': '08:00:00',
                    'pattern': r'^(\\d+):[0-5]\\d:[0-5]\\d
    """Formulaire unique pour tous les pointages (matin, après-midi, nuit/garde)"""
    class Meta:
        model = Pointage
        fields = [
            'employe', 'site', 'date_pointage', 'periode', 'type_journee',
            'heure_arrivee', 'heure_depart', 'statut', 'notes'
        ]
        widgets = {
            'employe': forms.Select(attrs={'class': 'form-control'}),
            'site': forms.Select(attrs={'class': 'form-control'}),
            'date_pointage': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'periode': forms.Select(attrs={'class': 'form-control'}),
            'type_journee': forms.Select(attrs={'class': 'form-control'}),
            'heure_arrivee': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heure_depart': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'statut': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'employe': 'Employé',
            'site': 'Site',
            'date_pointage': 'Date',
            'periode': 'Période',
            'type_journee': 'Type de journée',
            'heure_arrivee': "Heure d'arrivée / début",
            'heure_depart': 'Heure de départ / fin',
            'statut': 'Statut',
            'notes': 'Notes',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrer les employés actifs
        self.fields['employe'].queryset = Employe.objects.filter(actif=True)
        # Par défaut, pour une création, type_journee = 'normal'
        if not self.instance.pk:
            self.fields['type_journee'].initial = 'normal'

    def clean(self):
        cleaned_data = super().clean()
        periode = cleaned_data.get('periode')
        type_journee = cleaned_data.get('type_journee')
        heure_arrivee = cleaned_data.get('heure_arrivee')
        heure_depart = cleaned_data.get('heure_depart')

        # Vérification cohérence période / type_journee
        if periode == 'nuit' and type_journee != 'garde':
            self.add_error('type_journee', "Pour une période de nuit, le type de journée doit être 'Garde de nuit'.")
        if periode != 'nuit' and type_journee == 'garde':
            self.add_error('type_journee', "Le type 'Garde de nuit' ne peut être utilisé qu'avec la période 'nuit'.")

        # Une nouvelle garde créée depuis l'admin représente un PLANNING :
        # elle doit rester vide jusqu'au scan réel. Les corrections d'une
        # garde existante passent par une instance déjà persistée.
        if not self.instance.pk and periode == 'nuit' and (heure_arrivee or heure_depart):
            self.add_error(
                None,
                "Pour planifier une garde, laissez les heures d'arrivée et de départ vides."
            )

        # Validation des heures
        if heure_arrivee and heure_depart:
            # Pour les nuits, on autorise le départ après minuit (heure <= heure_arrivee)
            if periode != 'nuit' and heure_depart <= heure_arrivee:
                self.add_error('heure_depart', "L'heure de départ doit être après l'heure d'arrivée.")
        return cleaned_data

class ScanForm(forms.Form):
    """Formulaire de scan (entrée manuelle du matricule)"""
    matricule = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Scannez le QR code ou entrez le matricule',
            'autofocus': True
        }),
        label='Matricule'
    )
    site = forms.ModelChoiceField(
        queryset=Site.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Site'
    )

    def clean_matricule(self):
        matricule = self.cleaned_data.get('matricule')
        try:
            Employe.objects.get(matricule=matricule, actif=True)
        except Employe.DoesNotExist:
            raise forms.ValidationError("Employé non trouvé ou inactif")
        return matricule
from .models import Poste

class PosteForm(forms.ModelForm):
    class Meta:
        model  = Poste
        fields = ['nom', 'description', 'couleur']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'couleur': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }
        labels = {
            'nom':         'Nom du poste',
            'description': 'Description',
            'couleur':     'Couleur',
        }
,
                }
            ),
        }
        labels = {
            'heure_debut_systeme': 'Début des scans autorisés',
            'heure_fin_systeme': 'Fin des scans autorisés',
            'heure_bascule_apres_midi': 'Bascule matin → après-midi',
            'heure_debut_garde': 'Début de garde par défaut',
            'heure_fin_garde': 'Fin de garde par défaut',
            'tolerance_minutes_defaut': 'Tolérance par défaut (minutes)',
            'seuil_depart_anticipe_minutes_defaut': 'Seuil départ anticipé (minutes)',
            'duree_journee_reference': 'Durée journalière de référence',
        }


class PointageForm(forms.ModelForm):
    """Formulaire unique pour tous les pointages (matin, après-midi, nuit/garde)"""
    class Meta:
        model = Pointage
        fields = [
            'employe', 'site', 'date_pointage', 'periode', 'type_journee',
            'heure_arrivee', 'heure_depart', 'statut', 'notes'
        ]
        widgets = {
            'employe': forms.Select(attrs={'class': 'form-control'}),
            'site': forms.Select(attrs={'class': 'form-control'}),
            'date_pointage': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'periode': forms.Select(attrs={'class': 'form-control'}),
            'type_journee': forms.Select(attrs={'class': 'form-control'}),
            'heure_arrivee': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heure_depart': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'statut': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'employe': 'Employé',
            'site': 'Site',
            'date_pointage': 'Date',
            'periode': 'Période',
            'type_journee': 'Type de journée',
            'heure_arrivee': "Heure d'arrivée / début",
            'heure_depart': 'Heure de départ / fin',
            'statut': 'Statut',
            'notes': 'Notes',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrer les employés actifs
        self.fields['employe'].queryset = Employe.objects.filter(actif=True)
        # Par défaut, pour une création, type_journee = 'normal'
        if not self.instance.pk:
            self.fields['type_journee'].initial = 'normal'

    def clean(self):
        cleaned_data = super().clean()
        periode = cleaned_data.get('periode')
        type_journee = cleaned_data.get('type_journee')
        heure_arrivee = cleaned_data.get('heure_arrivee')
        heure_depart = cleaned_data.get('heure_depart')

        # Vérification cohérence période / type_journee
        if periode == 'nuit' and type_journee != 'garde':
            self.add_error('type_journee', "Pour une période de nuit, le type de journée doit être 'Garde de nuit'.")
        if periode != 'nuit' and type_journee == 'garde':
            self.add_error('type_journee', "Le type 'Garde de nuit' ne peut être utilisé qu'avec la période 'nuit'.")

        # Une nouvelle garde créée depuis l'admin représente un PLANNING :
        # elle doit rester vide jusqu'au scan réel. Les corrections d'une
        # garde existante passent par une instance déjà persistée.
        if not self.instance.pk and periode == 'nuit' and (heure_arrivee or heure_depart):
            self.add_error(
                None,
                "Pour planifier une garde, laissez les heures d'arrivée et de départ vides."
            )

        # Validation des heures
        if heure_arrivee and heure_depart:
            # Pour les nuits, on autorise le départ après minuit (heure <= heure_arrivee)
            if periode != 'nuit' and heure_depart <= heure_arrivee:
                self.add_error('heure_depart', "L'heure de départ doit être après l'heure d'arrivée.")
        return cleaned_data

class ScanForm(forms.Form):
    """Formulaire de scan (entrée manuelle du matricule)"""
    matricule = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Scannez le QR code ou entrez le matricule',
            'autofocus': True
        }),
        label='Matricule'
    )
    site = forms.ModelChoiceField(
        queryset=Site.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Site'
    )

    def clean_matricule(self):
        matricule = self.cleaned_data.get('matricule')
        try:
            Employe.objects.get(matricule=matricule, actif=True)
        except Employe.DoesNotExist:
            raise forms.ValidationError("Employé non trouvé ou inactif")
        return matricule
from .models import Poste

class PosteForm(forms.ModelForm):
    class Meta:
        model  = Poste
        fields = ['nom', 'description', 'couleur']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'couleur': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }
        labels = {
            'nom':         'Nom du poste',
            'description': 'Description',
            'couleur':     'Couleur',
        }
