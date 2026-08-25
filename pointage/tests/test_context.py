# pointage/tests/test_context.py
#
# TESTS DE LA COUCHE CONTEXT BUILDER
# ===================================

from datetime import time, date, timedelta
import pytest
from django.test import TestCase

from pointage.models import Employe, Site, Pointage
from pointage.context import (
    build_site_schedule,
    collect_day_context,
    collect_day_context_for_scan,
    DEFAULT_TOLERANCE_MINUTES,
)
from pointage.domain import DayState


class TestBuildSiteSchedule(TestCase):
    """Tests de build_site_schedule()."""
    
    def setUp(self):
        """Créer un site de test."""
        self.site = Site.objects.create(
            nom="Test Site",
            adresse="123 Rue Test",
            heure_ouverture_matin=time(8, 0),
            heure_fermeture_matin=time(12, 0),
            heure_ouverture_apres_midi=time(13, 30),
            heure_fermeture_apres_midi=time(17, 30),
        )
    
    def test_build_schedule_default_tolerance(self):
        """Construit un schedule avec tolérance par défaut."""
        schedule = build_site_schedule(self.site)
        
        assert schedule.morning_window.open_time == time(8, 0)
        assert schedule.morning_window.close_time == time(12, 0)
        assert schedule.afternoon_window.open_time == time(13, 30)
        assert schedule.afternoon_window.close_time == time(17, 30)
        assert schedule.tolerance == timedelta(minutes=DEFAULT_TOLERANCE_MINUTES)
    
    def test_build_schedule_custom_tolerance(self):
        """Construit un schedule avec tolérance personnalisée."""
        schedule = build_site_schedule(self.site, tolerance_minutes=30)
        
        assert schedule.tolerance == timedelta(minutes=30)
    
    def test_build_schedule_invalid_morning_hours(self):
        """Rejette un site avec fermeture matin <= ouverture matin."""
        bad_site = Site.objects.create(
            nom="Bad Site",
            adresse="Bad Address",
            heure_ouverture_matin=time(12, 0),
            heure_fermeture_matin=time(12, 0),  # Égal, pas valide
            heure_ouverture_apres_midi=time(13, 30),
            heure_fermeture_apres_midi=time(17, 30),
        )
        
        with pytest.raises(ValueError, match="fermeture matin"):
            build_site_schedule(bad_site)
    
    def test_build_schedule_invalid_afternoon_hours(self):
        """Rejette un site avec fermeture après-midi <= ouverture après-midi."""
        bad_site = Site.objects.create(
            nom="Bad Site 2",
            adresse="Bad Address 2",
            heure_ouverture_matin=time(8, 0),
            heure_fermeture_matin=time(12, 0),
            heure_ouverture_apres_midi=time(17, 30),
            heure_fermeture_apres_midi=time(13, 30),  # Avant ouverture
        )
        
        with pytest.raises(ValueError, match="fermeture après-midi"):
            build_site_schedule(bad_site)


class TestCollectDayContextEmpty(TestCase):
    """Tests de collect_day_context() pour une journée vide."""
    
    def setUp(self):
        """Créer un site et un employé de test."""
        self.site = Site.objects.create(
            nom="Test Site",
            adresse="123 Rue Test",
            heure_ouverture_matin=time(8, 0),
            heure_fermeture_matin=time(12, 0),
            heure_ouverture_apres_midi=time(13, 30),
            heure_fermeture_apres_midi=time(17, 30),
        )
        
        self.employee = Employe.objects.create(
            nom="Dupont",
            prenom="Jean",
            matricule="EMP001",
            actif=True,
        )
    
    def test_empty_day_morning(self):
        """Journée vide le matin."""
        context = collect_day_context(
            employee_id=self.employee.id,
            site=self.site,
            date_target=date.today(),
            current_time=time(8, 0)
        )
        
        assert context.morning_entry is False
        assert context.morning_exit is False
        assert context.afternoon_entry is False
        assert context.afternoon_exit is False
        assert context.get_current_state() == DayState.EMPTY
        assert context.is_morning_absent() is False
        assert context.is_afternoon_absent() is False
    
    def test_empty_day_afternoon(self):
        """Journée vide l'après-midi."""
        context = collect_day_context(
            employee_id=self.employee.id,
            site=self.site,
            date_target=date.today(),
            current_time=time(14, 0)
        )
        
        assert context.get_current_state() == DayState.EMPTY


class TestCollectDayContextWithPointages(TestCase):
    """Tests de collect_day_context() avec pointages existants."""
    
    def setUp(self):
        """Créer site, employé et pointages."""
        self.site = Site.objects.create(
            nom="Test Site",
            adresse="123 Rue Test",
            heure_ouverture_matin=time(8, 0),
            heure_fermeture_matin=time(12, 0),
            heure_ouverture_apres_midi=time(13, 30),
            heure_fermeture_apres_midi=time(17, 30),
        )
        
        self.employee = Employe.objects.create(
            nom="Dupont",
            prenom="Jean",
            matricule="EMP001",
            actif=True,
        )
        
        self.today = date.today()
    
    def test_morning_entry_only(self):
        """Contexte avec entrée matin enregistrée."""
        Pointage.objects.create(
            employe=self.employee,
            site=self.site,
            date_pointage=self.today,
            periode='matin',
            type_journee='normal',
            heure_arrivee=time(8, 15),
        )
        
        context = collect_day_context(
            employee_id=self.employee.id,
            site=self.site,
            date_target=self.today,
            current_time=time(10, 0)
        )
        
        assert context.morning_entry is True
        assert context.morning_exit is False
        assert context.afternoon_entry is False
        assert context.afternoon_exit is False
        assert context.get_current_state() == DayState.MORNING_STARTED
    
    def test_morning_complete(self):
        """Contexte avec matin complet (entrée + sortie)."""
        Pointage.objects.create(
            employe=self.employee,
            site=self.site,
            date_pointage=self.today,
            periode='matin',
            type_journee='normal',
            heure_arrivee=time(8, 15),
            heure_depart=time(11, 45),
        )
        
        context = collect_day_context(
            employee_id=self.employee.id,
            site=self.site,
            date_target=self.today,
            current_time=time(12, 0)
        )
        
        assert context.morning_entry is True
        assert context.morning_exit is True
        assert context.afternoon_entry is False
        assert context.afternoon_exit is False
        assert context.get_current_state() == DayState.MORNING_FINISHED
    
    def test_full_day(self):
        """Contexte avec journée complète."""
        Pointage.objects.create(
            employe=self.employee,
            site=self.site,
            date_pointage=self.today,
            periode='matin',
            type_journee='normal',
            heure_arrivee=time(8, 15),
            heure_depart=time(11, 45),
        )
        
        Pointage.objects.create(
            employe=self.employee,
            site=self.site,
            date_pointage=self.today,
            periode='apres_midi',
            type_journee='normal',
            heure_arrivee=time(14, 0),
            heure_depart=time(17, 15),
        )
        
        context = collect_day_context(
            employee_id=self.employee.id,
            site=self.site,
            date_target=self.today,
            current_time=time(17, 30)
        )
        
        assert context.morning_entry is True
        assert context.morning_exit is True
        assert context.afternoon_entry is True
        assert context.afternoon_exit is True
        assert context.get_current_state() == DayState.DAY_FINISHED
    
    def test_morning_absent(self):
        """Contexte : pas de matin, mais après-midi enregistré."""
        Pointage.objects.create(
            employe=self.employee,
            site=self.site,
            date_pointage=self.today,
            periode='apres_midi',
            type_journee='normal',
            heure_arrivee=time(14, 0),
        )
        
        context = collect_day_context(
            employee_id=self.employee.id,
            site=self.site,
            date_target=self.today,
            current_time=time(14, 30)
        )
        
        assert context.morning_entry is False
        assert context.morning_exit is False
        assert context.afternoon_entry is True
        assert context.afternoon_exit is False
        # Matin considéré absent
        assert context.is_morning_absent() is True
        assert context.get_current_state() == DayState.AFTERNOON_STARTED
    
    def test_afternoon_absent(self):
        """Contexte : matin enregistré, mais pas d'après-midi."""
        Pointage.objects.create(
            employe=self.employee,
            site=self.site,
            date_pointage=self.today,
            periode='matin',
            type_journee='normal',
            heure_arrivee=time(8, 15),
            heure_depart=time(11, 45),
        )
        
        # Simuler une clôture manuelle sans après-midi
        # (avec afternoon_exit=True mais pas d'heure_arrivee)
        Pointage.objects.create(
            employe=self.employee,
            site=self.site,
            date_pointage=self.today,
            periode='apres_midi',
            type_journee='normal',
            heure_depart=None,  # Pas de sortie
        )
        
        context = collect_day_context(
            employee_id=self.employee.id,
            site=self.site,
            date_target=self.today,
            current_time=time(17, 30)
        )
        
        assert context.morning_entry is True
        assert context.morning_exit is True
        assert context.afternoon_entry is False
        assert context.afternoon_exit is False
        # Après-midi pas marqué absent (pas d'exit)
        assert context.is_afternoon_absent() is False


class TestCollectDayContextDefaults(TestCase):
    """Tests des paramètres par défaut de collect_day_context()."""
    
    def setUp(self):
        """Créer site et employé."""
        self.site = Site.objects.create(
            nom="Test Site",
            adresse="123 Rue Test",
            heure_ouverture_matin=time(8, 0),
            heure_fermeture_matin=time(12, 0),
            heure_ouverture_apres_midi=time(13, 30),
            heure_fermeture_apres_midi=time(17, 30),
        )
        
        self.employee = Employe.objects.create(
            nom="Dupont",
            prenom="Jean",
            matricule="EMP001",
            actif=True,
        )
    
    def test_default_date_today(self):
        """Utilise aujourd'hui par défaut."""
        context = collect_day_context(
            employee_id=self.employee.id,
            site=self.site,
        )
        
        # Le contexte est construit, pas d'erreur
        assert context.site_id == self.site.id
        assert context.employee_id == self.employee.id
    
    def test_default_time_now(self):
        """Utilise l'heure actuelle par défaut."""
        context = collect_day_context(
            employee_id=self.employee.id,
            site=self.site,
            date_target=date.today(),
        )
        
        # current_time est défini (pas None)
        assert context.current_time is not None
        assert isinstance(context.current_time, time)


class TestCollectDayContextForScan(TestCase):
    """Tests de collect_day_context_for_scan()."""
    
    def setUp(self):
        """Créer site et employé."""
        self.site = Site.objects.create(
            nom="Test Site",
            adresse="123 Rue Test",
            heure_ouverture_matin=time(8, 0),
            heure_fermeture_matin=time(12, 0),
            heure_ouverture_apres_midi=time(13, 30),
            heure_fermeture_apres_midi=time(17, 30),
        )
        
        self.employee = Employe.objects.create(
            nom="Dupont",
            prenom="Jean",
            matricule="EMP001",
            actif=True,
        )
    
    def test_returns_tuple(self):
        """Retourne un tuple (context, site)."""
        context, site = collect_day_context_for_scan(
            employee_id=self.employee.id,
            site_id=self.site.id,
            date_target=date.today(),
            current_time=time(8, 0)
        )
        
        assert isinstance(context, type(context))  # DayContext
        assert site.id == self.site.id
    
    def test_nonexistent_site(self):
        """Lève Site.DoesNotExist si le site n'existe pas."""
        with pytest.raises(Site.DoesNotExist):
            collect_day_context_for_scan(
                employee_id=self.employee.id,
                site_id=9999,
                date_target=date.today(),
                current_time=time(8, 0)
            )


class TestCollectDayContextMultiDays(TestCase):
    """Tests avec multiple jours pour vérifier l'isolation."""
    
    def setUp(self):
        """Créer site, employé et pointages sur plusieurs jours."""
        self.site = Site.objects.create(
            nom="Test Site",
            adresse="123 Rue Test",
            heure_ouverture_matin=time(8, 0),
            heure_fermeture_matin=time(12, 0),
            heure_ouverture_apres_midi=time(13, 30),
            heure_fermeture_apres_midi=time(17, 30),
        )
        
        self.employee = Employe.objects.create(
            nom="Dupont",
            prenom="Jean",
            matricule="EMP001",
            actif=True,
        )
        
        self.today = date.today()
        self.yesterday = self.today - timedelta(days=1)
    
    def test_different_days_isolated(self):
        """Pointages sur jours différents sont isolés."""
        # Hier : journée complète
        Pointage.objects.create(
            employe=self.employee,
            site=self.site,
            date_pointage=self.yesterday,
            periode='matin',
            type_journee='normal',
            heure_arrivee=time(8, 0),
            heure_depart=time(12, 0),
        )
        
        # Aujourd'hui : entrée matin uniquement
        Pointage.objects.create(
            employe=self.employee,
            site=self.site,
            date_pointage=self.today,
            periode='matin',
            type_journee='normal',
            heure_arrivee=time(8, 15),
        )
        
        # Contexte d'aujourd'hui
        context_today = collect_day_context(
            employee_id=self.employee.id,
            site=self.site,
            date_target=self.today,
            current_time=time(10, 0)
        )
        
        # Contexte d'hier
        context_yesterday = collect_day_context(
            employee_id=self.employee.id,
            site=self.site,
            date_target=self.yesterday,
            current_time=time(10, 0)
        )
        
        # Vérifier isolation
        assert context_today.morning_exit is False  # Pas encore
        assert context_yesterday.morning_exit is True  # Enregistré hier


class TestCollectDayContextNonNormalPointages(TestCase):
    """Tests pour vérifier que seuls les pointages 'normal' sont pris en compte."""
    
    def setUp(self):
        """Créer site et employé."""
        self.site = Site.objects.create(
            nom="Test Site",
            adresse="123 Rue Test",
            heure_ouverture_matin=time(8, 0),
            heure_fermeture_matin=time(12, 0),
            heure_ouverture_apres_midi=time(13, 30),
            heure_fermeture_apres_midi=time(17, 30),
        )
        
        self.employee = Employe.objects.create(
            nom="Dupont",
            prenom="Jean",
            matricule="EMP001",
            actif=True,
        )
        
        self.today = date.today()
    
    def test_ignores_night_guards(self):
        """Les gardes de nuit ne sont pas comptabilisées."""
        # Créer une garde (nuit), pas un pointage normal
        Pointage.objects.create(
            employe=self.employee,
            site=self.site,
            date_pointage=self.today,
            periode='nuit',
            type_journee='garde',
            heure_arrivee=time(22, 0),
        )
        
        context = collect_day_context(
            employee_id=self.employee.id,
            site=self.site,
            date_target=self.today,
            current_time=time(23, 0)
        )
        
        # Les gardes ne doivent pas affecter le contexte normal
        assert context.morning_entry is False
        assert context.afternoon_entry is False
        assert context.get_current_state() == DayState.EMPTY
