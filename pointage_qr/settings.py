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

# ============================================================
# TEMPLATES - AJOUT DU CONTEXT PROCESSOR
# ============================================================
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
                'pointage.context_processors.dashboard_context',
                'pointage.context_processors.admin_badge_counts',
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


# settings.py

# ============================================================
# CONFIGURATION JAZZMIN — Version Premium avec Navigation + Badges
# ============================================================
JAZZMIN_SETTINGS = {
    "custom_css": "admin/css/jazzmin-badges.css",
    "custom_js": "admin/js/jazzmin-badges.js", 
    # ── Identité ──
    "site_title": "Pointage Admin",
    "site_header": "Pointage QR",
    "site_brand": "Pointage QR",
    "welcome_sign": "Bienvenue dans l'administration",
    "copyright": "Pointage QR © 2026",
    
    # ── Icônes ──
    "icons": {
        "auth": "fas fa-lock",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "pointage.Employe": "fas fa-users",
        "pointage.Pointage": "fas fa-clock-rotate-left",
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
    
    # ── Dashboard personnalisé ──
    "dashboard": "admin/index.html",
    
    # ============================================================
    # MENU PERSONNALISÉ DE LA SIDEBAR (Navigation complète)
    # ============================================================
    "navigation": [
        {
            "name": "📊 Tableau de bord",
            "icon": "fas fa-chart-line",
            "url": "admin:index",
            "permissions": ["auth.view_user"],
        },
        {
            "name": "👥 Employés",
            "icon": "fas fa-users",
            "children": [
                {
                    "name": "Tous les employés",
                    "icon": "fas fa-list",
                    "url": "admin:pointage_employe_changelist",
                },
                {
                    "name": "✅ Actifs",
                    "icon": "fas fa-user-check",
                    "url": "admin:pointage_employe_changelist?actif__exact=1",
                },
                {
                    "name": "⛔ Inactifs",
                    "icon": "fas fa-user-slash",
                    "url": "admin:pointage_employe_changelist?actif__exact=0",
                },
                {
                    "name": "➕ Ajouter un employé",
                    "icon": "fas fa-user-plus",
                    "url": "admin:pointage_employe_add",
                },
            ],
        },
        {
            "name": "📋 Pointages",
            "icon": "fas fa-clock",
            "children": [
                {
                    "name": "Tous les pointages",
                    "icon": "fas fa-list",
                    "url": "admin:pointage_pointage_changelist",
                },
                {
                    "name": "✅ Présents",
                    "icon": "fas fa-check-circle",
                    "url": "admin:pointage_pointage_changelist?statut__exact=present",
                },
                {
                    "name": "⚠️ Retards",
                    "icon": "fas fa-clock",
                    "url": "admin:pointage_pointage_changelist?statut__exact=retard",
                },
                {
                    "name": "❌ Absents",
                    "icon": "fas fa-times-circle",
                    "url": "admin:pointage_pointage_changelist?statut__exact=absent",
                },
                {
                    "name": "🌙 Gardes de nuit",
                    "icon": "fas fa-moon",
                    "url": "admin:pointage_pointage_changelist?periode__exact=nuit",
                },
            ],
        },
        {
            "name": "⚠️ Anomalies",
            "icon": "fas fa-triangle-exclamation",
            # ============================================================
            # BADGE DYNAMIQUE POUR LES ANOMALIES OUVERTES
            # ============================================================
            "badge": "anomalies_ouvertes",  # ← Context processor
            "badge_class": "badge-danger",   # ← Classe CSS (rouge)
            # ============================================================
            "children": [
                {
                    "name": "🔴 Ouvertes",
                    "icon": "fas fa-circle-exclamation",
                    "url": "admin:pointage_anomaliepointage_changelist?statut__exact=ouverte",
                },
                {
                    "name": "🟡 Traitées",
                    "icon": "fas fa-check",
                    "url": "admin:pointage_anomaliepointage_changelist?statut__exact=traitee",
                },
                {
                    "name": "✅ Clôturées",
                    "icon": "fas fa-check-double",
                    "url": "admin:pointage_anomaliepointage_changelist?statut__exact=cloturee",
                },
                {
                    "name": "Toutes les anomalies",
                    "icon": "fas fa-list",
                    "url": "admin:pointage_anomaliepointage_changelist",
                },
            ],
        },
        {
            "name": "🏢 Sites",
            "icon": "fas fa-building",
            "children": [
                {
                    "name": "Tous les sites",
                    "icon": "fas fa-list",
                    "url": "admin:pointage_site_changelist",
                },
                {
                    "name": "➕ Ajouter un site",
                    "icon": "fas fa-plus-circle",
                    "url": "admin:pointage_site_add",
                },
            ],
        },
        {
            "name": "💼 Postes",
            "icon": "fas fa-briefcase",
            "children": [
                {
                    "name": "Tous les postes",
                    "icon": "fas fa-list",
                    "url": "admin:pointage_poste_changelist",
                },
                {
                    "name": "➕ Ajouter un poste",
                    "icon": "fas fa-plus-circle",
                    "url": "admin:pointage_poste_add",
                },
            ],
        },
        {
            "name": "📦 Demandes",
            "icon": "fas fa-inbox",
            # ============================================================
            # BADGE DYNAMIQUE POUR LES DEMANDES EN ATTENTE
            # ============================================================
            "badge": "demandes_attente",    # ← Context processor
            "badge_class": "badge-danger",  # ← Classe CSS (rouge)
            # ============================================================
            "url": "admin:pointage_demandemodification_changelist",
        },
        {
            "name": "📱 Scans",
            "icon": "fas fa-qrcode",
            "url": "admin:pointage_scan_changelist",
        },
        {
            "name": "🔐 Utilisateurs",
            "icon": "fas fa-user-cog",
            "url": "admin:auth_user_changelist",
        },
    ],
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
    "brand_colour": "navbar-dark",
    "accent": "accent-primary",
    
    # ── Navbar ──
    "navbar": "navbar-white navbar-light",
    "no_navbar_border": False,
    "navbar_fixed": True,
    
    # ── Layout ──
    "layout_boxed": False,
    "footer_fixed": False,
    
    # ── Sidebar ──
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
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