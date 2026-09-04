# pointage/urls.py
from django.urls import path, include
from django.views.generic import RedirectView
from . import views
from .dashboard_hardening import dashboard, index
from .views import (
    employe_create_view, employe_update_view, employe_delete_view,
    site_create_view, site_update_view, site_delete_view,
    poste_create_view, poste_update_view, poste_delete_view,

    # Classes
    EmployeListView,
    SiteListView,
    PointageListView, PointageDetailView, PointageDeleteView,
    PosteListView,

    # API
    get_statut_journee, get_prochain_scan,
    get_dashboard_stats, get_charts_data, employe_qr_data,
)
from .admin_security import (
    alertes_rh_view,
    alerte_detail_view,
    export_resume_excel,
    admin_badge_counts_api,
    notifications_api as admin_notifications_api,
    scanner_view,
    RHAnomaliePointageViewSet,
)
from .admin_anomaly_workflow import admin_anomaly_workflow
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'anomalies', RHAnomaliePointageViewSet, basename='anomalie')

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='dashboard', permanent=False), name='root'),
    path('dashboard/', dashboard, name='dashboard'),
    path('index/', index, name='index'),

    # Employés
    path('employes/', EmployeListView.as_view(), name='employes'),
    path('employes/nouveau/', employe_create_view, name='employe_create'),
    path('employes/<int:pk>/update/', employe_update_view, name='employe_update'),
    path('employes/<int:pk>/delete/', employe_delete_view, name='employe_delete'),

    # Sites
    path('sites/', SiteListView.as_view(), name='sites'),
    path('sites/nouveau/', site_create_view, name='site_create'),
    path('sites/<int:pk>/modifier/', site_update_view, name='site_update'),
    path('sites/<int:pk>/supprimer/', site_delete_view, name='site_delete'),

    # Pointages
    path('pointages/', PointageListView.as_view(), name='pointages'),
    path('pointages/<int:pk>/', PointageDetailView.as_view(), name='pointage_detail'),
    path('pointages/<int:pk>/supprimer/', PointageDeleteView.as_view(), name='pointage_supprimer'),
    path('pointages/export/resume/', export_resume_excel, name='export_resume_excel'),

    # Postes
    path('postes/', PosteListView.as_view(), name='postes'),
    path('postes/nouveau/', poste_create_view, name='poste_create'),
    path('postes/<int:pk>/modifier/', poste_update_view, name='poste_update'),
    path('postes/<int:pk>/supprimer/', poste_delete_view, name='poste_delete'),

    # Scanner
    path('scanner/', scanner_view, name='scanner'),

    # Anomalies Web
    path('anomalies/', alertes_rh_view, name='alertes_rh'),
    path('anomalies/<int:pk>/', alerte_detail_view, name='alerte_detail'),

    # Workflow anomalie dans l'espace /admin/ (fallback après admin.site.urls)
    path('admin/pointage/anomaliepointage/<int:pk>/workflow/', admin_anomaly_workflow, name='admin_anomaly_workflow'),

    # API
    path('api/', include(router.urls)),
    path('api/employe-qr-data/<str:matricule>/', employe_qr_data, name='employe_qr_data'),
    path('api/statut-journee/<int:employe_id>/', get_statut_journee, name='statut_journee'),
    path('api/prochain-scan/<int:employe_id>/', get_prochain_scan, name='prochain_scan'),
    path('api/dashboard-stats/', get_dashboard_stats, name='dashboard_stats'),
    path('api/charts-data/', get_charts_data, name='charts_data'),
    path('api/admin-badge-counts/', admin_badge_counts_api, name='admin_badge_counts_api'),
    # L'application Web conserve son endpoint de notifications indépendant.
    path('api/notifications/', views.notifications_api, name='notifications_api'),
    # Jazzmin utilise explicitement cet endpoint séparé pour rester dans /admin/.
    path('api/admin-notifications/', admin_notifications_api, name='admin_notifications_api'),
]
