from django.test import TestCase
from datetime import time
from .services import parse_qr_data, SEUIL_MIDI


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
        result = parse_qr_data('  EMPLOYE:EMP001:token  ')
        self.assertIsNotNone(result)
        self.assertEqual(result['matricule'], 'EMP001')


class ConstantsTests(TestCase):
    def test_seuil_midi(self):
        self.assertEqual(SEUIL_MIDI, time(12, 30))
