"""
Tests pour parse_qr_data (pointage/services.py).

Relocalisé depuis l'ancien pointage/tests.py (fichier orphelin en conflit
de nommage avec le package pointage/tests/ — pytest ne pouvait plus le
collecter du tout : "import file mismatch", donc ces 3 tests n'étaient
plus jamais exécutés silencieusement).

test_parse_whitespace_handling utilise désormais un vrai token UUID :
depuis la correction "QR invalide -> jamais de 500", parse_qr_data()
rejette tout token qui n'est pas un UUID valide (cf. services.py).
L'ancienne version du test utilisait le token arbitraire 'token', qui
échouerait maintenant à juste titre.
"""
from django.test import TestCase
from ..services import parse_qr_data


class ParseQRDataTests(TestCase):
    def test_parse_valid_qr(self):
        result = parse_qr_data('EMPLOYE:EMP001:550e8400-e29b-41d4-a716-446655440000')
        self.assertIsNotNone(result)
        self.assertEqual(result['matricule'], 'EMP001')
        self.assertEqual(result['token'], '550e8400-e29b-41d4-a716-446655440000')

    def test_parse_invalid_format(self):
        self.assertIsNone(parse_qr_data('INVALID:EMP001:token'))
        self.assertIsNone(parse_qr_data('EMP001:token'))
        self.assertIsNone(parse_qr_data(''))

    def test_parse_whitespace_handling(self):
        result = parse_qr_data('  EMPLOYE:EMP001:550e8400-e29b-41d4-a716-446655440000  ')
        self.assertIsNotNone(result)
        self.assertEqual(result['matricule'], 'EMP001')

    def test_parse_token_not_a_uuid(self):
        """Un token non-UUID doit être rejeté proprement (pas de 500 côté DB)."""
        self.assertIsNone(parse_qr_data('EMPLOYE:EMP001:token'))
