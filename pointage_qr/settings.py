# settings.py — version corrigée

import os
import sys
from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=True, cast=bool)

ADMIN_SECRET_CODE = config('ADMIN_SECRET_CODE', default='1811')

# ── Hosts / réseau ───────────────────────────────────────────────────────────
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

CORS_ALLOWED_ORIGINS = config(
    'CORS_EXTRA_ORIGINS',
    default='http://localhost:8000,http://127.0.0.1:8000,http://pointageqr.local:8000',
    cast=Csv(),
)
CORS_ALLOW_ALL_ORIGINS = DEBUG

CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type',
    'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with',
]

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
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'


# ============================================================
# CONFIGURATION JAZZMIN — Version Premium
# ============================================================
JAZZMIN_SETTINGS = {
    # ── Identité ──
    "site_title": "Pointage Admin",
    "site_header": "Pointage QR",
    "site_brand": "Pointage QR",
    "welcome_sign": "Bienvenue dans l'administration",
    "copyright": "Pointage QR © 2026",
    
    # ── Icônes modernes ──
    "icons": {
        "auth": "fas fa-lock",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "pointage.Employe": "fas fa-id-badge",
        "pointage.Pointage": "fas fa-clock",
        "pointage.Site": "fas fa-building",
        "pointage.Scan": "fas fa-qrcode",
        "pointage.Poste": "fas fa-briefcase",
        "pointage.AnomaliePointage": "fas fa-triangle-exclamation",
        "pointage.DemandeModification": "fas fa-pen-to-square",
    },
    
    # ── Liens du menu supérieur ──
    "topmenu_links": [
        {"name": "App Web", "url": "/", "new_window": False},
    ],
    
    "usermenu_links": [
        {"name": "App Web", "url": "/", "icon": "fas fa-home"},
    ],
    
    # ── Organisation de la sidebar ──
    "show_sidebar": True,
    "navigation_expanded": True,
    
    # ── Cacher les modèles inutiles ──
    "hide_models": [
        "authtoken.token",
        "authtoken.tokenproxy",
    ],
    
    "hide_apps": [],
    
    "order_with_respect_to": [
        "auth",
        "pointage",
    ],
    
    "default_icon_parents": "fas fa-folder",
    "default_icon_children": "fas fa-circle",
    
    "dark_mode_theme": None,
    
    "search_model": "pointage.Employe",
    "user_avatar": None,
}
# ============================================================
# JAZZMIN UI TWEAKS — Version Premium
# ============================================================
JAZZMIN_UI_TWEAKS = {
    # ── Tailles ──
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    
    # ── Couleurs ──
    "brand_colour": "navbar-dark",     # Sidebar foncée
    "accent": "accent-primary",        # Accent bleu
    
    # ── Navbar ──
    "navbar": "navbar-white navbar-light",
    "no_navbar_border": False,
    "navbar_fixed": True,
    
    # ── Layout ──
    "layout_boxed": False,
    "footer_fixed": False,
    
    # ── Sidebar (bleu foncé cohérent avec l'UI) ──
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",     # ← Bleu foncé
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,       # ← IMPORTANT : Ne pas désactiver
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": True,
    
    # ── Thème ──
    "theme": "flatly",
    "dark_mode_theme": None,
    
    # ── Boutons ──
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-outline-secondary",
        "info": "btn-outline-info",
        "warning": "btn-outline-warning",
        "danger": "btn-outline-danger",
        "success": "btn-success",
    },
}