# pointage/tests/test_demandes_modification_views.py
#
# Point 9 : approuver_demande_view / refuser_demande_view n'avaient aucun
# test, bien que le code impose déjà correctement is_staff et empêche de
# retraiter une demande déjà tranchée. Ce fichier couvre ces garanties.
from django.test import TestCase, Client
from django.urls import reverse

from pointage.models import CustomUser, DemandeModification


class DemandeModificationViewsTestCase(TestCase):
    def setUp(self):
        self.staff_user = CustomUser.objects.create_user(
            username='rh_demande', password='x', role='admin', is_staff=True,
        )
        self.utilisateur_normal = CustomUser.objects.create_user(
            username='normal_demande', password='x', role='employe', is_staff=False,
        )
        self.demandeur = CustomUser.objects.create_user(
            username='demandeur_test', password='x', role='employe', is_staff=False,
        )
        self.demande = DemandeModification.objects.create(
            demandeur=self.demandeur, type_action='create', cible='poste',
            donnees={'nom': 'Nouveau Poste', 'couleur': '#2563EB'},
        )
        self.client = Client()

    def test_utilisateur_non_staff_ne_peut_pas_approuver(self):
        self.client.force_login(self.utilisateur_normal)
        self.client.post(reverse('admin:demande_approuver', args=[self.demande.pk]))
        self.demande.refresh_from_db()
        assert self.demande.statut == 'en_attente'

    def test_utilisateur_non_staff_ne_peut_pas_refuser(self):
        self.client.force_login(self.utilisateur_normal)
        self.client.post(reverse('admin:demande_refuser', args=[self.demande.pk]))
        self.demande.refresh_from_db()
        assert self.demande.statut == 'en_attente'

    def test_staff_peut_approuver(self):
        self.client.force_login(self.staff_user)
        self.client.post(reverse('admin:demande_approuver', args=[self.demande.pk]))
        self.demande.refresh_from_db()
        assert self.demande.statut == 'approuvee'
        assert self.demande.traitee_par == self.staff_user
        assert self.demande.date_traitement is not None

    def test_staff_peut_refuser(self):
        self.client.force_login(self.staff_user)
        self.client.post(reverse('admin:demande_refuser', args=[self.demande.pk]))
        self.demande.refresh_from_db()
        assert self.demande.statut == 'refusee'

    def test_une_demande_deja_traitee_ne_peut_pas_etre_retraitee(self):
        self.demande.statut = 'approuvee'
        self.demande.save()
        self.client.force_login(self.staff_user)
        self.client.post(reverse('admin:demande_refuser', args=[self.demande.pk]))
        self.demande.refresh_from_db()
        # Doit rester 'approuvee', pas basculer vers 'refusee'
        assert self.demande.statut == 'approuvee'

    def test_anonyme_ne_peut_pas_approuver(self):
        response = self.client.post(reverse('admin:demande_approuver', args=[self.demande.pk]))
        assert response.status_code == 302
        self.demande.refresh_from_db()
        assert self.demande.statut == 'en_attente'
