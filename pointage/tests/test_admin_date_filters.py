# pointage/tests/test_admin_date_filters.py
#
# Vérifie que DateDebutFilter / DateFinFilter (pointage/admin.py) filtrent
# réellement le queryset de l'admin Pointages, avec les cas :
#   - date début seule -> à partir de cette date (incluse)
#   - date fin seule    -> jusqu'à cette date (incluse)
#   - date début + fin  -> intervalle inclusif des deux côtés
#   - dates identiques  -> uniquement ce jour-là
#   - aucun résultat    -> queryset vide, pas d'erreur
#   - dates dans le mauvais ordre -> queryset vide, pas d'erreur
#   - valeur invalide   -> filtre ignoré, pas de crash
from datetime import date, time as dtime

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from pointage.admin import DateDebutFilter, DateFinFilter, PointageAdmin
from pointage.models import Employe, Pointage, Site


class DateFiltersTestCase(TestCase):
    def setUp(self):
        self.employe = Employe.objects.create(nom="Rakoto", prenom="Jean", matricule="E030", actif=True)
        self.site = Site.objects.create(
            nom="Site", adresse="a",
            heure_ouverture_matin=dtime(8, 0), heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 30), heure_fermeture_apres_midi=dtime(17, 30),
        )
        for jour in (date(2026, 8, 1), date(2026, 8, 5), date(2026, 8, 10)):
            Pointage.objects.create(
                employe=self.employe, site=self.site, date_pointage=jour,
                periode='matin', type_journee='normal', heure_arrivee=dtime(8, 0),
            )

    def _queryset(self):
        return Pointage.objects.all()

    def _apply(self, filter_cls, value):
        request = RequestFactory().get('/admin/pointage/pointage/', {filter_cls.parameter_name: value})
        f = filter_cls(request, request.GET.copy(), Pointage, PointageAdmin(Pointage, AdminSite()))
        return f.queryset(request, self._queryset())


class TestDateDebutFilter(DateFiltersTestCase):
    def test_date_debut_seule_retourne_a_partir_de_cette_date(self):
        result = self._apply(DateDebutFilter, '2026-08-05')
        self.assertEqual(
            set(result.values_list('date_pointage', flat=True)),
            {date(2026, 8, 5), date(2026, 8, 10)},
        )

    def test_date_debut_egale_a_une_date_existante_incluse(self):
        result = self._apply(DateDebutFilter, '2026-08-10')
        self.assertEqual(list(result.values_list('date_pointage', flat=True)), [date(2026, 8, 10)])

    def test_date_debut_sans_resultat(self):
        result = self._apply(DateDebutFilter, '2026-09-01')
        self.assertEqual(result.count(), 0)

    def test_date_debut_valeur_invalide_ignoree(self):
        result = self._apply(DateDebutFilter, 'not-a-date')
        self.assertEqual(result.count(), 3)

    def test_date_debut_absente_ne_filtre_pas(self):
        result = self._apply(DateDebutFilter, '')
        self.assertEqual(result.count(), 3)


class TestDateFinFilter(DateFiltersTestCase):
    def test_date_fin_seule_retourne_jusqua_cette_date(self):
        result = self._apply(DateFinFilter, '2026-08-05')
        self.assertEqual(
            set(result.values_list('date_pointage', flat=True)),
            {date(2026, 8, 1), date(2026, 8, 5)},
        )

    def test_date_fin_inclut_le_jour_meme(self):
        result = self._apply(DateFinFilter, '2026-08-01')
        self.assertEqual(list(result.values_list('date_pointage', flat=True)), [date(2026, 8, 1)])

    def test_date_fin_sans_resultat(self):
        result = self._apply(DateFinFilter, '2026-07-01')
        self.assertEqual(result.count(), 0)


class TestDateDebutEtFinCombinees(DateFiltersTestCase):
    def _fin(self, queryset, value):
        request = RequestFactory().get('/', {'date_fin': value})
        return DateFinFilter(
            request, request.GET.copy(), Pointage, PointageAdmin(Pointage, AdminSite())
        ).queryset(request, queryset)

    def test_intervalle_complet(self):
        queryset = self._apply(DateDebutFilter, '2026-08-02')
        queryset = self._fin(queryset, '2026-08-09')
        self.assertEqual(
            list(queryset.values_list('date_pointage', flat=True)), [date(2026, 8, 5)],
        )

    def test_dates_identiques_ne_retourne_que_ce_jour(self):
        queryset = self._apply(DateDebutFilter, '2026-08-05')
        queryset = self._fin(queryset, '2026-08-05')
        self.assertEqual(list(queryset.values_list('date_pointage', flat=True)), [date(2026, 8, 5)])

    def test_dates_dans_le_mauvais_ordre_ne_leve_pas_derreur_et_ne_retourne_rien(self):
        queryset = self._apply(DateDebutFilter, '2026-08-10')
        queryset = self._fin(queryset, '2026-08-01')
        self.assertEqual(queryset.count(), 0)
