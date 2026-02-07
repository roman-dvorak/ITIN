from django.contrib import admin
from django.views.generic import RedirectView
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path("", include("inventory.urls")),
    path("assets/", RedirectView.as_view(pattern_name="inventory:asset-list", permanent=False)),
    path("accounts/", include("allauth.urls")),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs-swagger"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="api-schema"), name="api-docs-redoc"),
    path("api/", include("inventory.api_urls")),
]
