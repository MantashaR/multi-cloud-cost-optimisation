from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("accounts", views.CloudAccountViewSet, basename="account")
router.register("costs", views.CostRecordViewSet, basename="cost-record")
router.register("anomalies", views.AnomalyViewSet, basename="anomaly")
router.register("forecasts", views.ForecastViewSet, basename="forecast")
router.register("recommendations", views.RecommendationViewSet, basename="recommendation")
router.register("analysis-runs", views.AnalysisRunViewSet, basename="analysis-run")

urlpatterns = [
    path("dashboard/", views._dashboard_view, name="dashboard"),
    path("", include(router.urls)),
]
