from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    help = (
        "[MÉCANISME SECONDAIRE] Depuis la migration vers le login "
        "utilisateur (POST /api/mobile/auth/login/), ce compte n'est plus "
        "le flux principal d'authentification mobile/desktop — chaque "
        "opérateur se connecte désormais avec son propre compte Django. "
        "Cette commande reste disponible et fonctionnelle (le jeton généré "
        "continue de fonctionner sur tous les endpoints protégés) "
        "uniquement si un scénario de terminal partagé/kiosque sans login "
        "individuel est un jour nécessaire. Ce compte n'est PAS un compte "
        "RH : il ne sert qu'à identifier un appareil, pas un utilisateur."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--username', type=str, default='scanner_device',
            help="Nom du compte de service (défaut : scanner_device)",
        )
        parser.add_argument(
            '--regenerate', action='store_true',
            help="Révoque l'ancien jeton et en génère un nouveau.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username']

        user, created = User.objects.get_or_create(
            username=username,
            defaults={'is_staff': False, 'is_active': True},
        )
        if created:
            user.set_unusable_password()  # jamais de connexion interactive avec ce compte
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Compte de service '{username}' créé."))
        else:
            self.stdout.write(f"Compte de service '{username}' déjà existant.")

        if options['regenerate']:
            Token.objects.filter(user=user).delete()
            self.stdout.write(self.style.WARNING("Ancien jeton révoqué."))

        token, created = Token.objects.get_or_create(user=user)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Jeton API du scanner :"))
        self.stdout.write(self.style.HTTP_INFO(token.key))
        self.stdout.write("")
        self.stdout.write(
            "À configurer côté mobile (app.json / variable d'environnement Expo) "
            "et côté desktop (config locale) — jamais en dur dans le code source."
        )
