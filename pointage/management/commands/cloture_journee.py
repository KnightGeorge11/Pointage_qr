from django.core.management.base import BaseCommand
from pointage.utils import cloture_journee
from datetime import date


class Command(BaseCommand):
    help = 'Détecte les scans manquants en fin de journée et crée des alertes RH'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Date cible au format YYYY-MM-DD (défaut : aujourd\'hui)',
        )

    def handle(self, *args, **options):
        date_str = options.get('date')
        if date_str:
            from datetime import datetime
            try:
                cible = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                self.stderr.write(self.style.ERROR(f'Format de date invalide: {date_str} (attendu: YYYY-MM-DD)'))
                return
        else:
            cible = date.today()

        self.stdout.write(f'Exécution de la clôture pour le {cible}...')
        resultat = cloture_journee(date=cible)
        self.stdout.write(self.style.SUCCESS(
            f'Terminé — {resultat["employes_verifies"]} employés vérifiés, '
            f'{resultat["alertes_crees"]} alertes créées.'
        ))
