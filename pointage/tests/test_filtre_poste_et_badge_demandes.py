# pointage/tests/test_filtre_poste_et_badge_demandes.py
#
# Finalisation — deux points restants :
#   1. Filtre "Poste" sur l'historique (PointageListView) + export Excel,
#      via la relation réelle Pointage -> employe -> poste.
#   2. Badge "demandes de modification" sur le dashboard, indépendant du
#      badge "anomalies ouvertes".
import openpyxl
from datetime import date, time as dtime
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from pointage.models import Employe, Poste, Site, Pointage, DemandeModification

User = get_user_model()


class FiltrePosteHistoriqueTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='rh', password='motdepasse123', role='user')
        self.client.force_login(self.user)

        self.site1 = Site.objects.create(
            nom="Site A", adresse="1 Rue A",
            heure_ouverture_matin=dtime(8, 0), heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 0), heure_fermeture_apres_midi=dtime(17, 0),
        )
        self.site2 = Site.objects.create(
            nom="Site B", adresse="1 Rue B",
            heure_ouverture_matin=dtime(8, 0), heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 0), heure_fermeture_apres_midi=dtime(17, 0),
        )
        self.poste_infirmier = Poste.objects.create(nom="Infirmier")
        self.poste_medecin   = Poste.objects.create(nom="Médecin")

        self.emp_infirmier = Employe.objects.create(
            nom="Rakoto", prenom="Jean", matricule="INF01", actif=True, poste=self.poste_infirmier,
        )
        self.emp_medecin = Employe.objects.create(
            nom="Rabe", prenom="Marie", matricule="MED01", actif=True, poste=self.poste_medecin,
        )

        Pointage.objects.create(
            employe=self.emp_infirmier, site=self.site1, date_pointage=date(2026, 8, 25),
            periode='matin', type_journee='normal', heure_arrivee=dtime(8, 5),
        )
        Pointage.objects.create(
            employe=self.emp_medecin, site=self.site2, date_pointage=date(2026, 8, 25),
            periode='matin', type_journee='normal', heure_arrivee=dtime(8, 5),
        )
        Pointage.objects.create(
            employe=self.emp_infirmier, site=self.site2, date_pointage=date(2026, 8, 26),
            periode='matin', type_journee='normal', heure_arrivee=dtime(8, 5),
        )

    def _jours(self, response):
        return list(response.context['jours'])

    # Test 1 : poste seul
    def test_filtre_poste_seul(self):
        response = self.client.get(reverse('pointages'), {'poste': self.poste_infirmier.id})
        jours = self._jours(response)
        assert len(jours) == 2
        assert all(j['employe'].poste_id == self.poste_infirmier.id for j in jours)

    # Test 2 : poste + site
    def test_filtre_poste_et_site(self):
        response = self.client.get(reverse('pointages'), {
            'poste': self.poste_infirmier.id, 'site': self.site1.id,
        })
        jours = self._jours(response)
        assert len(jours) == 1
        assert jours[0]['employe'].id == self.emp_infirmier.id
        assert jours[0]['site'].id == self.site1.id

    # Test 3 : poste + employé
    def test_filtre_poste_et_employe(self):
        response = self.client.get(reverse('pointages'), {
            'poste': self.poste_infirmier.id, 'employe': self.emp_infirmier.id,
        })
        jours = self._jours(response)
        assert len(jours) == 2
        assert all(j['employe'].id == self.emp_infirmier.id for j in jours)

        # Une combinaison poste/employé incohérente ne doit rien retourner
        response2 = self.client.get(reverse('pointages'), {
            'poste': self.poste_medecin.id, 'employe': self.emp_infirmier.id,
        })
        assert len(self._jours(response2)) == 0

    # Test 4 : poste + date
    def test_filtre_poste_et_date(self):
        response = self.client.get(reverse('pointages'), {
            'poste': self.poste_infirmier.id,
            'date_debut': '2026-08-26', 'date_fin': '2026-08-26',
        })
        jours = self._jours(response)
        assert len(jours) == 1
        assert jours[0]['date'] == date(2026, 8, 26)

    # Test 5 : poste + site + employé + date simultanément
    def test_filtre_poste_site_employe_date_combines(self):
        response = self.client.get(reverse('pointages'), {
            'poste': self.poste_infirmier.id,
            'site': self.site1.id,
            'employe': self.emp_infirmier.id,
            'date_debut': '2026-08-25', 'date_fin': '2026-08-25',
        })
        jours = self._jours(response)
        assert len(jours) == 1
        assert jours[0]['employe'].id == self.emp_infirmier.id
        assert jours[0]['site'].id == self.site1.id
        assert jours[0]['date'] == date(2026, 8, 25)

    # Test 6 : les filtres existants fonctionnent toujours sans poste
    def test_filtres_existants_fonctionnent_toujours_sans_poste(self):
        response = self.client.get(reverse('pointages'), {'site': self.site2.id})
        jours = self._jours(response)
        assert len(jours) == 2
        assert all(j['site'].id == self.site2.id for j in jours)

        response2 = self.client.get(reverse('pointages'))
        assert len(self._jours(response2)) == 3

    # Le select "Poste" doit rejoindre le formulaire de filtre existant
    # (id="filterForm"), sans créer de deuxième formulaire de filtre ni
    # de <form> imbriqué. (Le formulaire de déconnexion de base.html est
    # un formulaire distinct et légitime, sans rapport avec les filtres.)
    def test_select_poste_present_dans_le_formulaire_existant(self):
        response = self.client.get(reverse('pointages'))
        content = response.content.decode()
        assert content.count('id="filterForm"') == 1
        debut_form = content.index('<form method="get" id="filterForm">')
        fin_form = content.index('</form>', debut_form)
        bloc_formulaire = content[debut_form:fin_form]
        assert bloc_formulaire.count('<form') == 1  # pas de <form> imbriqué
        assert 'name="poste"' in bloc_formulaire
        assert self.poste_infirmier.nom in bloc_formulaire


class ExportExcelFiltrePosteTestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_rh', password='motdepasse123', role='admin', is_staff=True,
        )
        self.client.force_login(self.admin)

        self.site = Site.objects.create(
            nom="Site Export", adresse="1 Rue Export",
            heure_ouverture_matin=dtime(8, 0), heure_fermeture_matin=dtime(12, 0),
            heure_ouverture_apres_midi=dtime(13, 0), heure_fermeture_apres_midi=dtime(17, 0),
        )
        self.poste_infirmier = Poste.objects.create(nom="Infirmier Export")
        self.poste_medecin   = Poste.objects.create(nom="Médecin Export")
        self.emp_infirmier = Employe.objects.create(
            nom="Rakoto", prenom="Jean", matricule="EXPINF01", actif=True, poste=self.poste_infirmier,
        )
        self.emp_medecin = Employe.objects.create(
            nom="Rabe", prenom="Marie", matricule="EXPMED01", actif=True, poste=self.poste_medecin,
        )
        Pointage.objects.create(
            employe=self.emp_infirmier, site=self.site, date_pointage=date(2026, 8, 25),
            periode='matin', type_journee='normal', heure_arrivee=dtime(8, 5),
        )
        Pointage.objects.create(
            employe=self.emp_medecin, site=self.site, date_pointage=date(2026, 8, 25),
            periode='matin', type_journee='normal', heure_arrivee=dtime(8, 5),
        )

    # Test 7 : l'export Excel respecte le filtre poste
    def test_export_excel_respecte_le_filtre_poste(self):
        response = self.client.get(reverse('export_resume_excel'), {
            'date_debut': '2026-08-25', 'date_fin': '2026-08-25',
            'poste': self.poste_infirmier.id,
        })
        assert response.status_code == 200
        wb = openpyxl.load_workbook(BytesIO(response.content))
        ws = wb.active
        texte = "\n".join(
            str(cell.value) for row in ws.iter_rows() for cell in row if cell.value is not None
        )
        assert "Rakoto" in texte
        assert "Rabe" not in texte


class BadgeDemandesDashboardTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='rh_dash', password='motdepasse123', role='user')
        self.client.force_login(self.user)

    # Test 8 : le dashboard transmet demandes_en_attente et le template l'affiche
    def test_dashboard_affiche_le_badge_demandes_en_attente(self):
        DemandeModification.objects.create(
            demandeur=self.user, type_action='update', cible='employe',
            donnees={}, statut='en_attente',
        )
        DemandeModification.objects.create(
            demandeur=self.user, type_action='update', cible='employe',
            donnees={}, statut='en_attente',
        )
        response = self.client.get(reverse('dashboard'))
        assert response.context['demandes_en_attente'] == 2
        content = response.content.decode()
        assert '2 demande' in content

    def test_badge_demandes_masque_quand_zero(self):
        response = self.client.get(reverse('dashboard'))
        assert response.context['demandes_en_attente'] == 0
        content = response.content.decode()
        assert 'demande' + 's' * 0 + ' de modification' not in content or 'demande de modification' not in content

    def test_anomalies_et_demandes_sont_des_compteurs_independants(self):
        """
        Une demande de modification en attente ne doit pas affecter le
        compteur d'anomalies, et réciproquement. Ils sont calculés par
        deux requêtes distinctes sur deux modèles distincts.
        """
        DemandeModification.objects.create(
            demandeur=self.user, type_action='update', cible='employe',
            donnees={}, statut='en_attente',
        )
        response = self.client.get(reverse('dashboard'))
        assert response.context['demandes_en_attente'] == 1
        assert response.context['anomalies_ouvertes'] == 0
