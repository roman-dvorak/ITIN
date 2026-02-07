from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.urls import reverse

from .models import (
    Asset,
    AssetOS,
    GuestDevice,
    IPAddress,
    Network,
    NetworkInterface,
    OrganizationalGroup,
    OSFamily,
    OSVersion,
    Port,
)

User = get_user_model()


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_staff", "is_superuser")
    search_fields = ("email", "first_name", "last_name")

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
    list_display = ("name", "asset_type", "status", "owner")
    list_filter = ("asset_type", "status")
    search_fields = ("name", "asset_tag", "serial_number")
    filter_horizontal = ("groups",)
    inlines = [AssetOSInline]

    def view_on_site(self, obj):
        return obj.get_absolute_url()


@admin.register(OSFamily)
class OSFamilyAdmin(admin.ModelAdmin):
    list_display = ("name", "vendor", "platform_type", "supports_domain_join")
    list_filter = ("platform_type", "supports_domain_join")
    search_fields = ("name", "vendor")


@admin.register(OSVersion)
class OSVersionAdmin(admin.ModelAdmin):
    list_display = ("family", "version", "codename", "is_lts", "end_of_support_date")
    list_filter = ("family", "is_lts")
    search_fields = ("version", "codename", "kernel_version")


@admin.register(Network)
class NetworkAdmin(admin.ModelAdmin):
    list_display = ("name", "cidr", "vlan_id", "dhcp_enabled")
    list_filter = ("dhcp_enabled",)
    search_fields = ("name", "cidr")


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


@admin.register(GuestDevice)
class GuestDeviceAdmin(admin.ModelAdmin):
    list_display = ("mac_address", "sponsor", "valid_from", "valid_until", "enabled")
    list_filter = ("enabled",)
    search_fields = ("mac_address", "description", "sponsor__email")
    filter_horizontal = ("groups",)
