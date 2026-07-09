from rest_framework import serializers
from .models import Employe, Site, Pointage, Scan, Poste
from django.utils import timezone
from datetime import datetime, timedelta, time

class PosteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Poste
        fields = '__all__'

class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = '__all__'

class EmployeSerializer(serializers.ModelSerializer):
    sites_details = SiteSerializer(source='sites', many=True, read_only=True)
    poste_details = PosteSerializer(source='poste', read_only=True)
    
    class Meta:
        model = Employe
        fields = '__all__'
        read_only_fields = ['qr_code', 'qr_code_token', 'date_creation']

class PointageSerializer(serializers.ModelSerializer):
    employe_nom_complet = serializers.CharField(source='employe.__str__', read_only=True)
    site_nom = serializers.CharField(source='site.nom', read_only=True)
    periode_display = serializers.CharField(source='get_periode_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    type_journee_display = serializers.CharField(source='get_type_journee_display', read_only=True)
    
    class Meta:
        model = Pointage
        fields = '__all__'
        read_only_fields = ['retard', 'heures_travaillees', 'date_creation', 'date_modification']
    
    def validate(self, data):
        """Validation personnalisée pour les pointages"""
        if data.get('heure_arrivee') and data.get('heure_depart'):
            if data['heure_depart'] <= data['heure_arrivee']:
                # Exception pour les gardes de nuit (départ le lendemain)
                if data.get('periode') != 'nuit':
                    raise serializers.ValidationError(
                        "L'heure de départ doit être après l'heure d'arrivée"
                    )
        
        # Vérifier si un pointage existe déjà pour cet employé, date et période
        if self.instance is None:  # Création uniquement
            existe = Pointage.objects.filter(
                employe=data.get('employe'),
                date_pointage=data.get('date_pointage'),
                periode=data.get('periode')
            ).exists()
            
            if existe:
                raise serializers.ValidationError(
                    f"Un pointage existe déjà pour cet employé à la période {data.get('periode')}"
                )
        
        return data

class PointageDetailSerializer(PointageSerializer):
    employe_details = EmployeSerializer(source='employe', read_only=True)
    site_details = SiteSerializer(source='site', read_only=True)
    scans_details = serializers.SerializerMethodField()
    
    def get_scans_details(self, obj):
        scans = obj.scans.filter(actif=True).order_by('timestamp')
        return ScanSerializer(scans, many=True, read_only=True).data
    
    class Meta:
        model = Pointage
        fields = '__all__'

class ScanSerializer(serializers.ModelSerializer):
    employe_matricule = serializers.CharField(write_only=True, required=False)
    site_id = serializers.IntegerField(write_only=True, required=False)
    employe_nom_complet = serializers.CharField(source='employe.__str__', read_only=True)
    site_nom = serializers.CharField(source='site.nom', read_only=True)
    type_scan_display = serializers.CharField(source='get_type_scan_display', read_only=True)
    timestamp_local = serializers.SerializerMethodField()
    
    class Meta:
        model = Scan
        fields = [
            'id', 'employe', 'employe_matricule', 'site', 'site_id',
            'timestamp', 'timestamp_local', 'type_scan', 'type_scan_display',
            'pointage', 'employe_nom_complet', 'site_nom'
        ]
        read_only_fields = ['employe', 'site', 'timestamp', 'type_scan', 'pointage']
    
    def get_timestamp_local(self, obj):
        return timezone.localtime(obj.timestamp).isoformat()
    
    def determine_periode(self, heure_courante):
        """Détermine la période (matin/après-midi) basée sur l'heure"""
        heure_seuil_apres_midi = time(12, 0)
        return 'apres_midi' if heure_courante >= heure_seuil_apres_midi else 'matin'
    
    def determine_type_scan(self, pointage, periode):
        """Détermine le type de scan basé sur l'état du pointage (pour pointages normaux)"""
        if not pointage.heure_arrivee:
            return 'entree_matin' if periode == 'matin' else 'entree_apres_midi'
        elif not pointage.heure_depart:
            return 'sortie_matin' if periode == 'matin' else 'sortie_apres_midi'
        return None
    
    def create(self, validated_data):
        # Extraire les données d'entrée
        matricule = validated_data.pop('employe_matricule', None)
        site_id = validated_data.pop('site_id', None)
        
        # Récupérer l'employé
        if matricule:
            try:
                employe = Employe.objects.get(matricule=matricule, actif=True)
            except Employe.DoesNotExist:
                raise serializers.ValidationError({
                    "employe_matricule": "Employé non trouvé ou inactif"
                })
        elif validated_data.get('employe'):
            employe = validated_data.get('employe')
        else:
            raise serializers.ValidationError({
                "employe": "Employé requis"
            })
        
        # Récupérer le site
        if site_id:
            try:
                site = Site.objects.get(id=site_id)
            except Site.DoesNotExist:
                raise serializers.ValidationError({
                    "site_id": "Site non trouvé"
                })
        elif validated_data.get('site'):
            site = validated_data.get('site')
        else:
            raise serializers.ValidationError({
                "site": "Site requis"
            })
        
        # Vérifier que l'employé est affecté au site
        if site not in employe.sites.all():
            raise serializers.ValidationError({
                "site": "Employé non affecté à ce site"
            })
        
        # Obtenir l'heure actuelle
        now_local = timezone.localtime(timezone.now())
        heure_courante = now_local.time()
        date_courante = now_local.date()
        
        # --- GESTION DES GARDES DE NUIT (pointages nuit) ---
        # Vérifier s'il existe une garde en cours (pointage nuit sans heure_depart)
        garde_en_cours = Pointage.objects.filter(
            employe=employe,
            date_pointage=date_courante,
            periode='nuit',
            type_journee='garde',
            heure_depart__isnull=True
        ).first()
        
        if garde_en_cours:
            # Fin de garde
            garde_en_cours.heure_depart = heure_courante
            garde_en_cours.save()
            type_scan = 'fin_garde'
            
            scan = Scan.objects.create(
                employe=employe,
                site=site,
                type_scan=type_scan,
                pointage=garde_en_cours,
                timestamp=now_local,
            )
            return scan
        
        # Vérifier s'il y a une garde planifiée sans heure_arrivee
        garde_planifiee = Pointage.objects.filter(
            employe=employe,
            date_pointage=date_courante,
            periode='nuit',
            type_journee='garde',
            heure_arrivee__isnull=True
        ).first()
        
        if garde_planifiee:
            # Début de garde
            garde_planifiee.heure_arrivee = heure_courante
            garde_planifiee.site = site
            garde_planifiee.save()
            type_scan = 'debut_garde'
            
            scan = Scan.objects.create(
                employe=employe,
                site=site,
                type_scan=type_scan,
                pointage=garde_planifiee,
                timestamp=now_local,
            )
            return scan
        
        # --- POINTAGES NORMAUX (matin/après-midi) ---
        periode = self.determine_periode(heure_courante)
        
        # Récupérer ou créer le pointage pour cette période
        pointage, created = Pointage.objects.get_or_create(
            employe=employe,
            date_pointage=date_courante,
            periode=periode,
            defaults={
                'site': site,
                'type_journee': 'normal'
            }
        )
        
        # Si le pointage existait déjà mais sur un autre site
        if not created and pointage.site != site:
            pointage.site = site
        
        # Déterminer le type de scan
        type_scan = self.determine_type_scan(pointage, periode)
        
        if not type_scan:
            raise serializers.ValidationError({
                "pointage": f"Tous les pointages pour le {periode} sont déjà effectués"
            })
        
        # Mettre à jour l'heure d'arrivée ou de départ
        if 'entree' in type_scan:
            pointage.heure_arrivee = heure_courante
        elif 'sortie' in type_scan:
            pointage.heure_depart = heure_courante
        
        # Sauvegarder le pointage
        pointage.save()
        
        # Créer le scan
        scan = Scan.objects.create(
            employe=employe,
            site=site,
            type_scan=type_scan,
            pointage=pointage,
            timestamp=now_local,
        )
        
        return scan

class StatutJourneeSerializer(serializers.Serializer):
    """Sérialiseur pour le statut de la journée d'un employé"""
    date = serializers.DateField()
    employe_id = serializers.IntegerField()
    
    matin = serializers.DictField()
    apres_midi = serializers.DictField()
    nuit = serializers.DictField()  # Remplacé 'garde' par 'nuit'
    
    heures_travaillees = serializers.DurationField()
    heures_supplementaires = serializers.DurationField()
    
    def get_heures_supplementaires(self, heures_travaillees):
        heures_normales = timedelta(hours=8)
        if heures_travaillees > heures_normales:
            return heures_travaillees - heures_normales
        return timedelta(0)

class StatistiquesSerializer(serializers.Serializer):
    """Sérialiseur pour les statistiques"""
    total_employes = serializers.IntegerField()
    presents_aujourdhui = serializers.IntegerField()
    absents_aujourdhui = serializers.IntegerField()
    retards_aujourdhui = serializers.IntegerField()
    gardes_en_cours = serializers.IntegerField()
    date = serializers.DateField()

class DashboardDataSerializer(serializers.Serializer):
    """Sérialiseur pour les données du dashboard"""
    daily_data = serializers.DictField()
    weekly_data = serializers.DictField()
    evolution_data = serializers.DictField()
    postes_data = serializers.ListField()