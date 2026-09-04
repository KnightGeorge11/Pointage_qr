# pointage_qr/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from pointage.views_login import login_view, logout_view

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────
    path('login/',   login_view,  name='login'),
    path('logout/',  logout_view, name='logout'),
    path('password-reset/', include('django.contrib.auth.urls')),

    # ── App principale ────────────────────────────────────────────────────
    # Placée avant /admin/ pour que l'actionnaire d'anomalie Jazzmin
    # /admin/pointage/anomaliepointage/<id>/workflow/ soit résolu par
    # pointage.urls. Les autres URLs /admin/ continuent vers Django admin.
    path('', include('pointage.urls')),

    # ── Admin Django ──────────────────────────────────────────────────────
    path('admin/', admin.site.urls),

    # ── API mobile ────────────────────────────────────────────────────────
    path('api/', include('pointage.urls_api')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)