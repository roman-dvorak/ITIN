from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api_views import (
    ApiLoginView,
    GuestApproveAPIView,
    GuestPendingApprovalAPIView,
    GuestRejectAPIView,
    GuestSelfRegistrationAPIView,
    AssetPortInterfaceCreateAPIView,
    AssetViewSet,
    BulkAssetUpdateAPIView,
    BulkInterfaceUpdateAPIView,
    GroupLookupAPIView,
    GroupMembershipViewSet,
    LocationViewSet,
    NetworkInterfaceViewSet,
    NetworkLookupAPIView,
    OSFamilyLookupAPIView,
    OSVersionLookupAPIView,
    PortViewSet,
    UserLookupAPIView,
    UserViewSet,
)

app_name = "inventory-api"

router = DefaultRouter()
router.register("assets", AssetViewSet, basename="asset")
router.register("locations", LocationViewSet, basename="location")
router.register("interfaces", NetworkInterfaceViewSet, basename="interface")
router.register("ports", PortViewSet, basename="port")
router.register("users", UserViewSet, basename="user")
router.register("group-memberships", GroupMembershipViewSet, basename="group-membership")

urlpatterns = [
    path("auth/login/", ApiLoginView.as_view(), name="api-login"),
    path("guests/register/", GuestSelfRegistrationAPIView.as_view(), name="guest-register"),
    path("guests/pending/", GuestPendingApprovalAPIView.as_view(), name="guest-pending"),
    path("guests/<int:pk>/approve/", GuestApproveAPIView.as_view(), name="guest-approve"),
    path("guests/<int:pk>/reject/", GuestRejectAPIView.as_view(), name="guest-reject"),
    path(
        "assets/<int:asset_id>/port-interface/",
        AssetPortInterfaceCreateAPIView.as_view(),
        name="asset-port-interface-create",
    ),
    path("assets/bulk_update/", BulkAssetUpdateAPIView.as_view(), name="asset-bulk-update"),
    path("interfaces/bulk_update/", BulkInterfaceUpdateAPIView.as_view(), name="interface-bulk-update"),
    path("", include(router.urls)),
    path("users-lookup/", UserLookupAPIView.as_view(), name="user-lookup"),
    path("groups/", GroupLookupAPIView.as_view(), name="group-lookup"),
    path("os-families/", OSFamilyLookupAPIView.as_view(), name="os-family-lookup"),
    path("os-versions/", OSVersionLookupAPIView.as_view(), name="os-version-lookup"),
    path("networks/", NetworkLookupAPIView.as_view(), name="network-lookup"),
]
