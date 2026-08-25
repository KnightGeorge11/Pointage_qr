# pointage/tests/test_coherence_matricule_qr.py
#
# Point 8 : si le matricule d'un employé est modifié, le QR physique
# (qui encode "EMPLOYE:matricule:token") doit être régénéré, sinon
# l'ancien badge imprimé cesse silencieusement de fonctionner.
from django.test import TestCase

from pointage.models import Employe


class CoherenceMatriculeQrTestCase(TestCase):
    def test_le_qr_est_genere_a_la_creation(self):
        employe = Employe.objects.create(nom="Test", prenom="QR", matricule="QR001", actif=True)
        assert employe.qr_code
        assert employe.qr_code.name.endswith('.png')

    def test_le_qr_est_regenere_quand_le_matricule_change(self):
        employe = Employe.objects.create(nom="Test", prenom="QR", matricule="QR002", actif=True)
        ancien_nom_fichier = employe.qr_code.name
        token_avant = employe.qr_code_token

        employe.matricule = "QR002-RENOMME"
        employe.save()
        employe.refresh_from_db()

        # Le fichier QR doit avoir été régénéré (nouveau nom, car le matricule
        # fait partie du nom de fichier généré par generer_qr_code()).
        assert employe.qr_code.name != ancien_nom_fichier
        # Le token UUID (l'ancrage réel de sécurité) ne doit JAMAIS changer.
        assert employe.qr_code_token == token_avant

    def test_le_qr_nest_pas_regenere_si_rien_ne_change(self):
        employe = Employe.objects.create(nom="Test", prenom="QR", matricule="QR003", actif=True)
        nom_fichier_avant = employe.qr_code.name

        employe.nom = "AutreNom"  # ne touche pas au matricule
        employe.save()
        employe.refresh_from_db()

        assert employe.qr_code.name == nom_fichier_avant
