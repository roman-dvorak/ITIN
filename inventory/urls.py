from django.urls import path

from .views import (
    AssetCreateView,
    AssetDetailView,
    AssetExportView,
    AssetImportView,
    AssetImportTemplateView,
    AssetEditView,
    AssetListView,
    AssetOverviewView,
    AssetOSCreateView,
    AssetOSUpdateView,
    AssetPortCreateView,
    AssetPortInterfaceCreateView,
    AssetPortInterfaceUpdateView,
    AssetPortUpdateView,
    HomeView,
    UserDetailView,
    UserListView,
)

app_name = "inventory"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("asset/", AssetListView.as_view(), name="asset-list"),
    path("asset/create/", AssetCreateView.as_view(), name="asset-create"),
    path("asset/export/", AssetExportView.as_view(), name="asset-export"),
    path("asset/import/", AssetImportView.as_view(), name="asset-import"),
    path("asset/import/template/", AssetImportTemplateView.as_view(), name="asset-import-template"),
    path("asset/<int:pk>/", AssetDetailView.as_view(), name="asset-detail"),
    path("asset/<int:pk>/edit/", AssetEditView.as_view(), name="asset-edit"),
    path("asset/<int:pk>/os/add/", AssetOSCreateView.as_view(), name="asset-os-add"),
    path("asset/<int:pk>/os/<int:os_id>/update/", AssetOSUpdateView.as_view(), name="asset-os-update"),
    path("asset/<int:pk>/port/add/", AssetPortCreateView.as_view(), name="asset-port-add"),
    path("asset/<int:pk>/port/<int:port_id>/update/", AssetPortUpdateView.as_view(), name="asset-port-update"),
    path(
        "asset/<int:pk>/port/<int:port_id>/interface/add/",
        AssetPortInterfaceCreateView.as_view(),
        name="asset-port-interface-add",
    ),
    path(
        "asset/<int:pk>/port/<int:port_id>/interface/<int:interface_id>/update/",
        AssetPortInterfaceUpdateView.as_view(),
        name="asset-port-interface-update",
    ),
    path("asset/overview/", AssetOverviewView.as_view(), name="asset-overview"),
    path("user/", UserListView.as_view(), name="user-list"),
    path("user/<int:pk>/", UserDetailView.as_view(), name="user-detail"),
]
