from rest_framework import serializers
from .models import Employe, Site, Pointage, Scan, Poste, AnomaliePointage, AnomalieTraitement
from .services import process_scan
from django.utils import timezone

class PosteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Poste
        fields = '__all__'

class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = '__all__'

class EmployeSerializer(serializers.ModelSerializer):
    poste_details = PosteSerializer(source='poste', read_only=True)
    
    class Meta:
        model = Employe
        # Le token QR est un secret d'authentification du badge : il ne doit
        # jamais être exposé par l'API générale des employés.
        fields = [
            field.name for field in model._meta.fields
            if field.name != 'qr_code_token'
        ] + ['poste_details']
        read_only_fields = ['qr_code', 'date_creation']

class PointageSerializer(serializers.ModelSerializer):
    employe_nom_complet = serializers.CharField(source='employe.__str__', read_only=True)
    site_nom = serializers.CharField(source='site.nom', read_only=True)
    periode_display = serializers.CharField(source='get_periode_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    type_journee_display = serializers.CharField(source='get_type_journee_display', read_only=True)

    # ── Entrée additionnelle pour la création via process_scan() ──────────
    # 'force_new' n'est pas un champ du modèle Pointage : c'est un paramètre
    # de process_scan() (démarrer une nouvelle garde même si une est déjà en
    # cours, cf. force_new_garde). Écriture seule : jamais renvoyé dans la
    # réponse.
    force_new = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Pointage
        fields = '__all__'
        read_only_fields = ['retard', 'heures_travaillees', 'date_creation', 'date_modification']
        extra_kwargs = {
            # date_pointage/periode sont désormais calculés par
            # process_scan() -> DayStateMachine à la création (ils ne
            # doivent plus être imposés par l'appelant) ; ils restent des
            # champs normaux, modifiables lors d'une correction manuelle
            # (PATCH/PUT, cf. update() par défaut de ModelSerializer).
            'date_pointage': {'required': False},
            'periode': {'required': False},
        }
        # DRF génère automatiquement un UniqueTogetherValidator à partir de
        # Meta.unique_together = ['employe', 'date_pointage', 'periode']
        # (cf. models.py), qui re-rend ces champs obligatoires en entrée
        # (contournant les extra_kwargs ci-dessus) et fait doublon avec la
        # garantie d'unicité déjà assurée par process_scan()
        # (_apply_scan_decision : select_for_update + get_or_create, sous
        # transaction). La contrainte unique_together elle-même reste
        # active au niveau base de données (filet de sécurité inchangé) ;
        # seule sa validation redondante ici est retirée.
        validators = []

    def validate(self, data):
        """Validation de forme uniquement.

        Toute décision métier (quelle période, quel type de scan, s'il
        existe déjà un pointage pour cet employé/date/période, anti-doublon,
        gestion garde/minuit...) appartient exclusivement à process_scan()
        / DayStateMachine, seule source de vérité pour la création d'un
        Pointage (cf. create() ci-dessous et services.py). L'ancienne
        vérification "un pointage existe déjà pour cette période -> erreur"
        a été retirée d'ici : elle était incorrecte pour le flux normal
        (un Pointage 'matin' incomplet doit pouvoir recevoir sa sortie, pas
        être rejeté), et process_scan()/DayStateMachine gère déjà ce cas
        correctement.
        """
        if data.get('heure_arrivee') and data.get('heure_depart'):
            if data['heure_depart'] <= data['heure_arrivee']:
                # Exception pour les gardes de nuit (départ le lendemain)
                if data.get('periode') != 'nuit':
                    raise serializers.ValidationError(
                        "L'heure de départ doit être après l'heure d'arrivée"
                    )
        return data

    def create(self, validated_data):
        """
        Unique point de création d'un Pointage via l'API REST
        (POST /api/pointages/, réservé à l'admin/RH — cf.
        PointageViewSet.get_permissions).

        Ne prend elle-même AUCUNE décision métier : elle traduit les
        données déjà validées en un appel à process_scan(), exactement
        comme le fait l'endpoint mobile (MobileRecordScanAPIView) et
        l'endpoint scanner web (ScanAPIView / scan_api_view). Un seul
        moteur de décision (DayStateMachine, via process_scan) pour toute
        création de pointage, quel que soit le point d'entrée :

            POST /api/mobile/scan/record/  -> process_scan() -> Pointage
            POST /api/pointages/           -> process_scan() -> Pointage
            (scanner web)                  -> process_scan() -> Pointage

        Il n'y a pas de QR physique scanné depuis ce endpoint : le token
        est récupéré directement sur l'employé déjà résolu par le
        serializer (PrimaryKeyRelatedField), ce qui préserve la même
        garantie de sécurité que le flux QR (l'employé est de toute façon
        identifié par sa PK, jamais par une saisie libre de matricule).
        """
        force_new = validated_data.pop('force_new', False)
        employe = validated_data.get('employe')
        site = validated_data.get('site')

        if employe is None:
            raise serializers.ValidationError({'employe': "Employé requis"})
        if site is None:
            raise serializers.ValidationError({'site': "Site requis"})

        # Mode dérivé de l'intention de l'appelant (garde vs pointage
        # normal) — même convention que MobileRecordScanAPIView/ScanAPIView.
        mode = 'garde' if (
            validated_data.get('periode') == 'nuit'
            or validated_data.get('type_journee') == 'garde'
        ) else 'auto'

        result = process_scan(
            matricule=employe.matricule,
            qr_token=str(employe.qr_code_token),
            site_id=site.id,
            mode=mode,
            force_new_garde=force_new,
        )

        if result['status'] != 'success':
            # warning (doublon, hors plage, refus métier...) ou error
            # (QR/site invalide) -> 400 côté DRF, avec le code et le
            # message produits par process_scan()/DayStateMachine.
            raise serializers.ValidationError({
                'detail': result['message'],
                'code': result.get('code'),
            })

        # process_scan() ne renvoie qu'un résumé (dict), pas l'instance —
        # on récupère le Pointage réellement écrit via le scan créé dans
        # la même transaction, pour que ModelSerializer puisse sérialiser
        # une réponse complète et cohérente avec le reste de l'API.
        scan = Scan.objects.select_related('pointage').get(id=result['data']['scan_id'])
        return scan.pointage

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

    def create(self, validated_data):
        """
        Délègue entièrement à process_scan() (services.py) — seule source
        de vérité pour toute décision de pointage, cf. PointageSerializer.create()
        et MobileRecordScanAPIView.

        L'implémentation précédente dupliquait ici son propre moteur de
        décision (determine_periode, determine_type_scan, détection/gestion
        de la garde en cours, get_or_create(Pointage), création directe de
        Scan) : un second chemin, indépendant de DayStateMachine, capable
        d'écrire un Pointage avec des règles potentiellement divergentes
        (aucune protection anti-doublon, aucune vérification de plage
        horaire, aucun enregistrement d'anomalie). Ce serializer n'est
        actuellement routé nulle part en écriture (pas de ScanViewSet/route
        exposant .create()) ; on l'aligne quand même sur l'architecture
        cible pour qu'il ne puisse plus jamais redevenir un second moteur
        de décision si un jour il est exposé.
        """
        matricule = validated_data.pop('employe_matricule', None)
        site_id = validated_data.pop('site_id', None)

        employe = validated_data.get('employe')
        if employe is None and matricule:
            try:
                employe = Employe.objects.get(matricule=matricule, actif=True)
            except Employe.DoesNotExist:
                raise serializers.ValidationError({
                    "employe_matricule": "Employé non trouvé ou inactif"
                })
        if employe is None:
            raise serializers.ValidationError({"employe": "Employé requis"})

        site = validated_data.get('site')
        if site is None and site_id:
            try:
                site = Site.objects.get(id=site_id)
            except Site.DoesNotExist:
                raise serializers.ValidationError({"site_id": "Site non trouvé"})
        if site is None:
            raise serializers.ValidationError({"site": "Site requis"})

        result = process_scan(
            matricule=employe.matricule,
            qr_token=str(employe.qr_code_token),
            site_id=site.id,
        )

        if result['status'] != 'success':
            raise serializers.ValidationError({
                'detail': result['message'],
                'code': result.get('code'),
            })

        return Scan.objects.get(id=result['data']['scan_id'])


# ============================================================
# ANOMALIES DE POINTAGE (Phase 4)
#
# En lecture uniquement de bout en bout : les anomalies sont créées par
# le moteur métier (services.py/anomalies.py), jamais via l'API. Seules
# les actions dédiées `traiter`/`clôturer` (AnomaliePointageViewSet)
# permettent de faire évoluer leur statut.

class AnomalieTraitementSerializer(serializers.ModelSerializer):
    administrateur_nom = serializers.CharField(source='administrateur.username', read_only=True, default=None)

    class Meta:
        model = AnomalieTraitement
        fields = [
            'id', 'administrateur', 'administrateur_nom', 'date_traitement',
            'commentaire', 'pointage_concerne', 'corrections',
        ]
        read_only_fields = fields


class AnomaliePointageSerializer(serializers.ModelSerializer):
    type_display    = serializers.CharField(source='get_type_display', read_only=True)
    statut_display  = serializers.CharField(source='get_statut_display', read_only=True)
    gravite         = serializers.CharField(read_only=True)
    gravite_display = serializers.CharField(source='get_gravite_display', read_only=True)
    employe_nom_complet = serializers.CharField(source='employe.get_nom_complet', read_only=True, default=None)
    site_nom        = serializers.CharField(source='site.nom', read_only=True, default=None)

    class Meta:
        model = AnomaliePointage
        fields = [
            'id', 'type', 'type_display', 'gravite', 'gravite_display',
            'employe', 'employe_nom_complet', 'matricule_scanne',
            'site', 'site_nom', 'date_pointage', 'message',
            'statut', 'statut_display', 'cloturee_par', 'date_cloture',
            'created_at',
        ]
        read_only_fields = fields


class AnomaliePointageDetailSerializer(AnomaliePointageSerializer):
    traitement = AnomalieTraitementSerializer(read_only=True)

    class Meta(AnomaliePointageSerializer.Meta):
        fields = AnomaliePointageSerializer.Meta.fields + ['contexte', 'traitement']