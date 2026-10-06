from django.contrib import admin
from django.urls import include, path

from costs.metrics import metrics_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("costs.urls")),
    path("metrics", metrics_view, name="prometheus-metrics"),
]
