from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .admin_security import secure_sensitive_apis
from .views_mobile import (
    MobileSitesAPIView,
    MobileCheckFirstScanAPIView,
    MobileRecordScanAPIView,
    MobileCurrentPeriodAPIView,
    MobilePointagesAPIView,
    MobileTodayPointagesAPIView,
    MobileTestAPIView,
    MobileLoginAPIView,
    MobileLogoutAPIView,
)

# Sécuriser les ViewSets et endpoints web généraux avant que le routeur ne
# transforme les classes/fonctions en URL patterns. Les routes mobiles
# restent protégées par leurs propres classes d'authentification.
secure_sensitive_apis()

router = DefaultRouter()
router.register(r'employes', views.EmployeViewSet, basename='employe')
router.register(r'sites', views.SiteViewSet, basename='site')
router.register(r'pointages', views.PointageViewSet, basename='pointage')

urlpatterns = [
    path('', include(router.urls)),

    # Endpoints API supplémentaires (pour l'application web)
    path('scanner/', views.ScanAPIView.as_view(), name='api_scanner'),
    path('scan/', views.scan_api_view, name='api_scan'),
    path('employe-qr-data/<str:matricule>/', views.employe_qr_data, name='employe_qr_data'),
    path('statut-journee/<int:employe_id>/', views.get_statut_journee, name='statut_journee'),
    path('prochain-scan/<int:employe_id>/', views.get_prochain_scan, name='prochain_scan'),
    path('dashboard-stats/', views.get_dashboard_stats, name='dashboard_stats'),
    path('charts-data/', views.get_charts_data, name='charts_data'),

    # API Mobile
    path('mobile/test/', MobileTestAPIView.as_view(), name='mobile_test'),
    path('mobile/auth/login/', MobileLoginAPIView.as_view(), name='mobile_login'),
    path('mobile/auth/logout/', MobileLogoutAPIView.as_view(), name='mobile_logout'),
    path('mobile/sites/', MobileSitesAPIView.as_view(), name='mobile_sites'),
    path('mobile/scan/check-first/', MobileCheckFirstScanAPIView.as_view(), name='mobile_check_first_scan'),
    path('mobile/scan/record/', MobileRecordScanAPIView.as_view(), name='mobile_record_scan'),
    path('mobile/periods/current/', MobileCurrentPeriodAPIView.as_view(), name='mobile_current_period'),
    path('mobile/pointages/', MobilePointagesAPIView.as_view(), name='mobile_pointages'),
    path('mobile/pointages/today/', MobileTodayPointagesAPIView.as_view(), name='mobile_pointages_today'),
]
