from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api_views import (
    AssetViewSet,
    BulkAssetUpdateAPIView,
    BulkInterfaceUpdateAPIView,
    GroupLookupAPIView,
    NetworkInterfaceViewSet,
    NetworkLookupAPIView,
    OSFamilyLookupAPIView,
    OSVersionLookupAPIView,
    PortViewSet,
    UserLookupAPIView,
)

app_name = "inventory-api"

router = DefaultRouter()
router.register("assets", AssetViewSet, basename="asset")
router.register("interfaces", NetworkInterfaceViewSet, basename="interface")
router.register("ports", PortViewSet, basename="port")

urlpatterns = [
    path("assets/bulk_update/", BulkAssetUpdateAPIView.as_view(), name="asset-bulk-update"),
    path("interfaces/bulk_update/", BulkInterfaceUpdateAPIView.as_view(), name="interface-bulk-update"),
    path("", include(router.urls)),
    path("users/", UserLookupAPIView.as_view(), name="user-lookup"),
    path("groups/", GroupLookupAPIView.as_view(), name="group-lookup"),
    path("os-families/", OSFamilyLookupAPIView.as_view(), name="os-family-lookup"),
    path("os-versions/", OSVersionLookupAPIView.as_view(), name="os-version-lookup"),
    path("networks/", NetworkLookupAPIView.as_view(), name="network-lookup"),
]
