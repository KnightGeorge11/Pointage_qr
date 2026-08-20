# urls_api.py (ou le nom de votre fichier d'API)
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views_mobile import (
    MobileSitesAPIView, 
    MobileCheckFirstScanAPIView, 
    MobileRecordScanAPIView,
    MobileCurrentPeriodAPIView,
    MobilePointagesAPIView,
    MobileTodayPointagesAPIView,
    MobileTestAPIView
)

# Créer un routeur pour les API
router = DefaultRouter()
router.register(r'employes', views.EmployeViewSet, basename='employe')
router.register(r'sites', views.SiteViewSet, basename='site')
router.register(r'pointages', views.PointageViewSet, basename='pointage')

urlpatterns = [
    # Inclure les routes du routeur
    path('', include(router.urls)),
    
    # Endpoints API supplémentaires (pour l'application web)
    path('scanner/', views.ScanAPIView.as_view(), name='api_scanner'),
    path('scan/', views.scan_api_view, name='api_scan'),
    path('employe-qr-data/<str:matricule>/', views.employe_qr_data, name='employe_qr_data'),
    path('statut-journee/<int:employe_id>/', views.get_statut_journee, name='statut_journee'),
    path('prochain-scan/<int:employe_id>/', views.get_prochain_scan, name='prochain_scan'),
    path('dashboard-stats/', views.get_dashboard_stats, name='dashboard_stats'),
    path('charts-data/', views.get_charts_data, name='charts_data'),
    
    # ✅ API Calendrier (si elles ne sont pas déjà dans pointage/urls.py)
    # NE PAS AJOUTER ICI SI DÉJÀ DANS pointage/urls.py
    # path('pointages-mois/', views.api_pointages_mois, name='api_pointages_mois'),
    # path('pointages-jour/', views.api_pointages_jour, name='api_pointages_jour'),
    
    # API Mobile (pour l'application React Native)
    path('mobile/test/', MobileTestAPIView.as_view(), name='mobile_test'),
    path('mobile/sites/', MobileSitesAPIView.as_view(), name='mobile_sites'),
    path('mobile/scan/check-first/', MobileCheckFirstScanAPIView.as_view(), name='mobile_check_first_scan'),
    path('mobile/scan/record/', MobileRecordScanAPIView.as_view(), name='mobile_record_scan'),
    path('mobile/periods/current/', MobileCurrentPeriodAPIView.as_view(), name='mobile_current_period'),
    path('mobile/pointages/', MobilePointagesAPIView.as_view(), name='mobile_pointages'),
    path('mobile/pointages/today/', MobileTodayPointagesAPIView.as_view(), name='mobile_pointages_today'),
]