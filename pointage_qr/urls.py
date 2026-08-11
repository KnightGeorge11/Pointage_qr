# pointage_qr/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from pointage.views_login import login_view, logout_view
from django.urls import path
from .admin import HistoriquePointagesView


urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────
    path('login/',   login_view,  name='login'),
    path('logout/',  logout_view, name='logout'),
    path('password-reset/', include('django.contrib.auth.urls')),

    # ── Admin Django ───────────────────────────────────────────────────────
    path('admin/', admin.site.urls),

    # ── API mobile ────────────────────────────────────────────────────────
    path('api/', include('pointage.urls_api')),

    # ── App principale (dashboard, scanner, historique…) ──────────────────
    path('', include('pointage.urls')),

    path('admin/historique-pointages/',
         HistoriquePointagesView.as_view(),
         name='admin:historique_pointages'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,  document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)