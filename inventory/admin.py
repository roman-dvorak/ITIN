from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.urls import reverse

from .models import (
    Asset,
    AssetOS,
    AssetTag,
    AssetTypeLifetime,
    GuestDevice,
    IPAddress,
    Location,
    Network,
    NetworkApprovalRequest,
    NetworkInterface,
    OrganizationalGroup,
    OSFamily,
    Port,
    TaskRun,
    UserProfile,
)

User = get_user_model()


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile"
    fields = ("metadata",)
    readonly_fields = ("metadata",)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_staff", "is_superuser", "has_entra_data")
    search_fields = ("email", "first_name", "last_name")
    inlines = [UserProfileInline]

    @admin.display(boolean=True, description="Entra Data")
    def has_entra_data(self, obj):
        try:
            return bool(obj.profile.metadata.get("entra"))
        except UserProfile.DoesNotExist:
            return False

    def view_on_site(self, obj):
        return reverse("inventory:user-detail", args=[obj.pk])


@admin.register(OrganizationalGroup)
class OrganizationalGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "default_vlan_id")
    search_fields = ("name",)
    filter_horizontal = ("members", "admins")


class AssetOSInline(admin.StackedInline):
    model = AssetOS
    extra = 0


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("name", "asset_type", "status", "owner", "location", "commissioning_date")
    list_filter = ("asset_type", "status", "location")
    search_fields = ("name", "asset_tag", "serial_number")
    autocomplete_fields = ("owner", "location")
    filter_horizontal = ("groups", "tags")
    inlines = [AssetOSInline]

    def view_on_site(self, obj):
        return obj.get_absolute_url()


@admin.register(OSFamily)
class OSFamilyAdmin(admin.ModelAdmin):
    list_display = ("name_flavor", "family", "support_status", "name", "flavor")
    list_filter = ("family", "support_status")
    search_fields = ("name", "flavor")
    fields = ("family", "name", "flavor", "support_status", "metadata")

    @admin.display(description="Name - Flavor")
    def name_flavor(self, obj):
        return obj.name_flavor


@admin.register(Network)
class NetworkAdmin(admin.ModelAdmin):
    list_display = ("name", "cidr", "vlan_id", "dhcp_enabled")
    list_filter = ("dhcp_enabled",)
    search_fields = ("name", "cidr")


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("path_label", "name", "slug", "parent", "updated_at")
    list_filter = ("groups",)
    search_fields = ("name", "slug", "path_cache", "parent__name")
    filter_horizontal = ("groups",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("path_cache", "id")

    @admin.display(description="Path", ordering="path_cache")
    def path_label(self, obj):
        return obj.path_label


@admin.register(NetworkInterface)
class NetworkInterfaceAdmin(admin.ModelAdmin):
    list_display = ("asset", "port", "identifier", "mac_address", "active")
    list_filter = ("active",)
    search_fields = ("asset__name", "identifier", "mac_address")


@admin.register(IPAddress)
class IPAddressAdmin(admin.ModelAdmin):
    list_display = ("address", "network", "status", "assigned_interface", "active")
    list_filter = ("status", "active", "network")
    search_fields = ("address", "hostname", "assigned_interface__asset__name")


@admin.register(Port)
class PortAdmin(admin.ModelAdmin):
    list_display = ("asset", "name", "port_kind", "active")
    list_filter = ("port_kind", "active")
    search_fields = ("asset__name", "name")


@admin.register(AssetTag)
class AssetTagAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


@admin.register(AssetTypeLifetime)
class AssetTypeLifetimeAdmin(admin.ModelAdmin):
    list_display = ("asset_type", "planned_lifetime_months")


@admin.register(NetworkApprovalRequest)
class NetworkApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ("asset", "status", "requested_by", "requested_at", "reviewed_by", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("asset__name",)


@admin.register(TaskRun)
class TaskRunAdmin(admin.ModelAdmin):
    list_display = ("task_name", "status", "started_at", "finished_at", "triggered_by")
    list_filter = ("status", "task_name")
    readonly_fields = ("task_name", "status", "started_at", "finished_at", "stdout", "result_data", "triggered_by")


@admin.register(GuestDevice)
class GuestDeviceAdmin(admin.ModelAdmin):
    list_display = (
        "device_name",
        "mac_address",
        "owner_email",
        "network",
        "sponsor",
        "approval_status",
        "valid_until",
        "enabled",
    )
    list_filter = ("approval_status", "enabled", "network")
    search_fields = ("device_name", "owner_name", "owner_email", "mac_address", "description", "sponsor__email")
    autocomplete_fields = ("sponsor", "approved_by", "network")
    filter_horizontal = ("groups",)
