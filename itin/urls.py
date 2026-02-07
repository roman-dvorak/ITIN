from django.contrib import admin
from django.views.generic import RedirectView
from django.urls import include, path

urlpatterns = [
    path("", include("inventory.urls")),
    path("assets/", RedirectView.as_view(pattern_name="inventory:asset-list", permanent=False)),
    path("accounts/", include("allauth.urls")),
    path("admin/", admin.site.urls),
    path("api/", include("inventory.api_urls")),
]
