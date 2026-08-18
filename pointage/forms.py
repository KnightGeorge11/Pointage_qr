# pointage/forms.py

from django import forms
from .models import Employe, Site, Pointage, Poste


class EmployeForm(forms.ModelForm):
    class Meta:
        model = Employe
        fields = ['poste', 'nom', 'prenom', 'matricule', 'actif']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control'}),
            'matricule': forms.TextInput(attrs={'class': 'form-control'}),
            'poste': forms.Select(attrs={'class': 'form-control'}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'poste': 'Poste',
            'nom': 'Nom',
            'prenom': 'Prénom',
            'matricule': 'Matricule',
            'actif': 'Actif',
        }


class SiteForm(forms.ModelForm):
    class Meta:
        model = Site
        fields = ['nom', 'adresse', 'heure_ouverture_matin', 'heure_fermeture_matin',
                 'heure_ouverture_apres_midi', 'heure_fermeture_apres_midi']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'heure_ouverture_matin': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heure_fermeture_matin': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heure_ouverture_apres_midi': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heure_fermeture_apres_midi': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        }
        labels = {
            'nom': 'Nom du site',
            'adresse': 'Adresse',
            'heure_ouverture_matin': "Heure d'ouverture (matin)",
            'heure_fermeture_matin': 'Heure de fermeture (matin)',
            'heure_ouverture_apres_midi': "Heure d'ouverture (après-midi)",
            'heure_fermeture_apres_midi': 'Heure de fermeture (après-midi)',
        }


class PosteForm(forms.ModelForm):
    class Meta:
        model = Poste
        fields = ['nom', 'description', 'couleur']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'couleur': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }
        labels = {
            'nom': 'Nom du poste',
            'description': 'Description',
            'couleur': 'Couleur',
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
        date_pointage = cleaned_data.get('date_pointage')

        # Vérification cohérence période / type_journee
        if periode == 'nuit' and type_journee != 'garde':
            self.add_error('type_journee', "Pour une période de nuit, le type de journée doit être 'Garde de nuit'.")
        if periode != 'nuit' and type_journee == 'garde':
            self.add_error('type_journee', "Le type 'Garde de nuit' ne peut être utilisé qu'avec la période 'nuit'.")

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
            employe = Employe.objects.get(matricule=matricule, actif=True)
        except Employe.DoesNotExist:
            raise forms.ValidationError("Employé non trouvé ou inactif")
        return matricule


# ============================================================
# NOUVEAU FORMULAIRE DE RECHERCHE DE DATE
# ============================================================

class DateSearchForm(forms.Form):
    """
    Formulaire de recherche de pointages par plage de dates.
    Utilise des champs de type 'date' qui affichent un calendrier.
    """
    date_debut = forms.DateField(
        label='Date de début',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'placeholder': 'jj/mm/aaaa'
        }),
        required=False
    )
    date_fin = forms.DateField(
        label='Date de fin',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'placeholder': 'jj/mm/aaaa'
        }),
        required=False
    )