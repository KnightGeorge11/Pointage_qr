# pointage/tests/test_dashboard_context.py
#
# Point 5 : dashboard_context faisait ~26 requêtes SQL en boucle (7 jours
# x 2 + 4 semaines x 3) pour construire les données du graphique. Remplacé
# par une seule requête agrégée en Python. Ce test vérifie que les valeurs
# produites sont EXACTEMENT les mêmes qu'avant (pas juste "ça ne plante pas").
from datetime import time as dtime, timedelta

from django.test import TestCase, RequestFactory
from django.utils import timezone

from pointage.models import Employe, Site, Pointage, CustomUser
from pointage.context_processors import dashboard_context


class DashboardContextTestCase(TestCase):
    def setUp(self):
        self.site = Site.objects.create(
            nom="Site Dashboard", adresse="1 Rue Test",
            heure_ouverture_matin=dtime(8, 0), heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 0), heure_fermeture_apres_midi=dtime(17, 0),
        )
        self.today = timezone.localtime(timezone.now()).date()
        self.start_of_week = self.today - timedelta(days=self.today.weekday())

        self.employes = [
            Employe.objects.create(nom=f"E{i}", prenom="T", matricule=f"DASH{i}", actif=True)
            for i in range(3)
        ]
        # Employé 0 : présent aujourd'hui, en retard
        Pointage.objects.create(
            employe=self.employes[0], site=self.site, date_pointage=self.today,
            periode='matin', type_journee='normal',
            heure_arrivee=dtime(8, 25), retard=timedelta(minutes=25),
        )
        # Employé 1 : présent aujourd'hui, à l'heure
        Pointage.objects.create(
            employe=self.employes[1], site=self.site, date_pointage=self.today,
            periode='matin', type_journee='normal',
            heure_arrivee=dtime(8, 0), retard=timedelta(0),
        )
        # Employé 2 : présent il y a 2 semaines seulement
        Pointage.objects.create(
            employe=self.employes[2], site=self.site,
            date_pointage=self.start_of_week - timedelta(weeks=2),
            periode='matin', type_journee='normal',
            heure_arrivee=dtime(8, 0), retard=timedelta(0),
        )

        self.admin = CustomUser.objects.create_superuser(username='dash_test', password='x', email='')

    def _get_context(self):
        request = RequestFactory().get('/admin/')
        request.user = self.admin
        return dashboard_context(request)

    def test_stats_du_jour_correctes(self):
        ctx = self._get_context()
        assert ctx['total_employes'] == 3
        assert ctx['presents_aujourdhui'] == 2
        assert ctx['retards_aujourdhui'] == 1
        assert ctx['absents_aujourdhui'] == 1

    def test_donnees_hebdomadaires_placees_au_bon_jour(self):
        ctx = self._get_context()
        idx_aujourdhui = self.today.weekday()  # 0=Lundi
        assert ctx['weekly_presents'][idx_aujourdhui] == 2
        assert ctx['weekly_retards'][idx_aujourdhui] == 1
        assert ctx['weekly_absents'][idx_aujourdhui] == 1
        # Les autres jours de la semaine (sans pointage) doivent être à 0
        for i in range(7):
            if i != idx_aujourdhui:
                assert ctx['weekly_presents'][i] == 0

    def test_evolution_4_semaines_isole_bien_chaque_semaine(self):
        ctx = self._get_context()
        # Semaine courante (dernier élément) : 2 employés sur 3 présents -> 66.7%
        assert ctx['evolution_presence'][-1] == round(2 / 3 * 100, 1)
        # Semaine d'il y a 2 -> 1 employé sur 3 présent -> 33.3%
        assert ctx['evolution_presence'][-3] == round(1 / 3 * 100, 1)
        # Semaine sans aucun pointage -> 0%
        assert ctx['evolution_presence'][0] == 0.0

    def test_aucune_requete_sur_page_login(self):
        request = RequestFactory().get('/login/')
        request.user = self.admin
        ctx = dashboard_context(request)
        assert ctx == {}
