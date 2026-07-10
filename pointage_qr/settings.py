# settings.py — version corrigée complète

import os
import sys
from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=True, cast=bool)

ADMIN_SECRET_CODE = config('ADMIN_SECRET_CODE', default='1811')

# ── Hosts / réseau ───────────────────────────────────────────────────────────
#
# Le serveur tourne sur un réseau local dont l'IP peut changer (attribution
# DHCP). Pour ne JAMAIS avoir à modifier ce fichier quand l'IP change,
# toute la configuration réseau se fait via le fichier .env
# (variable DJANGO_ALLOWED_HOSTS, liste separee par des virgules).
#
# Solution recommandee pour une IP qui ne bouge plus du tout :
#   1) Reserver une IP fixe pour la VM sur le routeur (bail DHCP statique),
#      OU configurer une IP statique dans Netplan sur la VM Ubuntu.
#   2) Installer avahi-daemon sur la VM (sudo apt install avahi-daemon)
#      pour pouvoir joindre le serveur via pointageqr.local quelle que
#      soit son IP - c'est la valeur ajoutee par defaut ci-dessous.
#   3) Mettre a jour .env UNE SEULE FOIS avec la ou les IP/hostnames actuels.
#      Voir NETWORK_SETUP.md a la racine du projet pour le detail.
#
# 'testserver' est necessaire pour django.test.Client (tests unitaires).
ALLOWED_HOSTS = config(
    'DJANGO_ALLOWED_HOSTS',
    default='localhost,127.0.0.1,pointageqr.local,testserver',
    cast=Csv(),
)

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'pointage',
    'corsheaders',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# CORS_ALLOWED_ORIGINS : mêmes IP/hostnames que ALLOWED_HOSTS, mais avec
# schéma + port. Configurable via .env (CORS_EXTRA_ORIGINS) sans jamais
# toucher au code. Les origines pour localhost/hostname mDNS sont incluses
# par défaut.
CORS_ALLOWED_ORIGINS = config(
    'CORS_EXTRA_ORIGINS',
    default='http://localhost:8000,http://127.0.0.1:8000,http://pointageqr.local:8000',
    cast=Csv(),
)
# En développement (DEBUG=True), on autorise toutes les origines locales
# pour ne pas bloquer les tests depuis un téléphone/PC dont l'IP change.
CORS_ALLOW_ALL_ORIGINS = DEBUG

CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type',
    'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with',
]

# CSRF_TRUSTED_ORIGINS : requis par Django dès qu'on soumet un formulaire
# (ex. connexion admin) depuis une origine autre que celle servie en local.
# Même logique : dérivé de CORS_ALLOWED_ORIGINS, configurable via .env.
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default=','.join(CORS_ALLOWED_ORIGINS),
    cast=Csv(),
)

ROOT_URLCONF = 'pointage_qr.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'pointage_qr.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='pointage_qr'),
        'USER': config('DB_USER', default='knight'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}
AUTH_USER_MODEL = 'pointage.CustomUser'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Indian/Antananarivo'
USE_I18N = True
USE_TZ = True

if 'runserver' in sys.argv:
    os.environ['TZ'] = 'Indian/Antananarivo'

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    # Par défaut : session pour l'app web, token pour l'app mobile
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    # Par défaut : authentifié requis — les exceptions déclarent AllowAny explicitement
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

LOGIN_URL          = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'


# ============================================================
# CONFIGURATION JAZZMIN
# ============================================================
JAZZMIN_SETTINGS = {
    "site_title":    "Pointage Admin",
    "site_header":   "Pointage",
    "site_brand":    "Pointage QR",
    "welcome_sign":  "Bienvenue dans l'administration",
    "copyright":     "Pointage QR © 2026",
    "theme":         "flatly",
    "dark_mode_theme": None,
    "icons": {
        "auth":                         "fas fa-users-cog",
        "auth.customuser":              "fas fa-user",
        "auth.Group":                   "fas fa-users",
        "pointage.Employe":             "fas fa-id-badge",
        "pointage.Pointage":            "fas fa-clock",
        "pointage.Site":                "fas fa-map-marker-alt",
        "pointage.Scan":                "fas fa-qrcode",
        "pointage.Poste":               "fas fa-briefcase",
        "pointage.DemandeModification": "fas fa-inbox",
    },
    "topmenu_links": [
        {"name": "App Web", "url": "/", "new_window": False},
    ],
    "usermenu_links": [
        {"name": "App Web", "url": "/", "icon": "fas fa-home"},
    ],
    "show_sidebar":        True,
    "navigation_expanded": True,
    "order_with_respect_to": [
        "auth",
        "pointage",
    ],
    "default_icon_parents":  "fas fa-folder",
    "default_icon_children": "fas fa-circle",
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text":          False,
    "footer_small_text":          False,
    "body_small_text":            False,
    "brand_small_text":           False,
    "brand_colour":               "navbar-light",
    "accent":                     "accent-primary",
    "navbar":                     "navbar-light navbar-white",  # ← navbar claire
    "no_navbar_border":           True,
    "navbar_fixed":               True,
    "layout_boxed":               False,
    "footer_fixed":               False,
    "sidebar_fixed":              True,
    "sidebar":                    "sidebar-light-primary", # ← sidebar claire
    "sidebar_nav_small_text":     False,
    "sidebar_disable_expand":     False,
    "sidebar_nav_child_indent":   True,
    "sidebar_nav_compact_style":  False,
    "sidebar_nav_legacy_style":   False,
    "sidebar_nav_flat_style":     True,   # ← style plat, plus moderne
    "theme":                      "flatly",
    "dark_mode_theme":            None,
    "button_classes": {
    "primary":   "btn-outline-primary",
    "secondary": "btn-outline-secondary",
    "info":      "btn-outline-info",
    "warning":   "btn-outline-warning",
    "danger":    "btn-outline-danger",
    "success":   "btn-outline-success", }
}
