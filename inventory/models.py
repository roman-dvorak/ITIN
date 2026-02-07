from __future__ import annotations

import ipaddress
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone

MAC_ADDRESS_RE = re.compile(r"^([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})$")


def normalize_mac(value: str) -> str:
    return value.lower().replace("-", ":")


def validate_mac(value: str) -> None:
    if not MAC_ADDRESS_RE.match(value):
        raise ValidationError("Invalid MAC address format.")


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class OrganizationalGroup(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    default_vlan_id = models.PositiveIntegerField(null=True, blank=True)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="asset_member_groups",
        blank=True,
    )
    admins = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="asset_admin_groups",
        blank=True,
    )

    def __str__(self) -> str:
        return self.name


class AssetQuerySet(models.QuerySet):
    def visible_to(self, user):
        if not user.is_authenticated:
            return self.none()
        if user.is_superuser:
            return self
        return self.filter(Q(groups__members=user) | Q(groups__admins=user)).distinct()

    def editable_by(self, user):
        if not user.is_authenticated:
            return self.none()
        if user.is_superuser:
            return self
        return self.filter(groups__admins=user).distinct()


class Asset(TimeStampedModel):
    class AssetType(models.TextChoices):
        COMPUTER = "COMPUTER", "Computer"
        NOTEBOOK = "NOTEBOOK", "Notebook"
        SERVER = "SERVER", "Server"
        MONITOR = "MONITOR", "Monitor"
        KEYBOARD = "KEYBOARD", "Keyboard"
        DEVICE = "DEVICE", "Device"
        NETWORK = "NETWORK", "Network"
        PRINTER = "PRINTER", "Printer"
        MOBILE = "MOBILE", "Mobile"
        TABLET = "TABLET", "Tablet"
        BYOD = "BYOD", "BYOD"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        STORED = "STORED", "Stored"
        RETIRED = "RETIRED", "Retired"
        LOST = "LOST", "Lost"

    name = models.CharField(max_length=200, blank=True)
    asset_type = models.CharField(
        max_length=20,
        choices=AssetType.choices,
        default=AssetType.COMPUTER,
    )
    asset_tag = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=120, blank=True)
    manufacturer = models.CharField(max_length=120, blank=True)
    model = models.CharField(max_length=120, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_assets",
        null=True,
        blank=True,
    )
    groups = models.ManyToManyField(OrganizationalGroup, related_name="assets", blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    objects = AssetQuerySet.as_manager()

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self):
        return reverse("inventory:asset-detail", args=[self.pk])

    @property
    def asset_os(self):
        """Backward-compatible access to the most recently saved OS record."""
        if hasattr(self, "_prefetched_objects_cache") and "os_entries" in self._prefetched_objects_cache:
            entries = self._prefetched_objects_cache["os_entries"]
            return entries[0] if entries else None
        return self.os_entries.select_related("family", "version").order_by("-id").first()


class OSFamily(models.Model):
    class PlatformType(models.TextChoices):
        DESKTOP = "DESKTOP", "Desktop"
        SERVER = "SERVER", "Server"
        MOBILE = "MOBILE", "Mobile"
        OTHER = "OTHER", "Other"

    name = models.CharField(max_length=120, unique=True)
    vendor = models.CharField(max_length=120, blank=True)
    platform_type = models.CharField(
        max_length=20,
        choices=PlatformType.choices,
        default=PlatformType.DESKTOP,
    )
    supports_domain_join = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.name


class OSVersion(models.Model):
    family = models.ForeignKey(OSFamily, on_delete=models.CASCADE, related_name="versions")
    version = models.CharField(max_length=100)
    codename = models.CharField(max_length=120, blank=True)
    release_date = models.DateField(null=True, blank=True)
    end_of_support_date = models.DateField(null=True, blank=True)
    is_lts = models.BooleanField(default=False)
    kernel_version = models.CharField(max_length=120, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["family", "version"], name="uniq_os_family_version")
        ]

    def __str__(self) -> str:
        return f"{self.family.name} {self.version}"


class AssetOS(models.Model):
    class SupportState(models.TextChoices):
        UNKNOWN = "UNKNOWN", "Unknown"
        SUPPORTED = "SUPPORTED", "Supported"
        EXTENDED = "EXTENDED", "Extended"
        EOL = "EOL", "End of life"

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="os_entries")
    family = models.ForeignKey(OSFamily, on_delete=models.PROTECT)
    version = models.ForeignKey(OSVersion, on_delete=models.PROTECT, null=True, blank=True)
    patch_level = models.CharField(max_length=120, blank=True)
    installed_on = models.DateField(null=True, blank=True)
    support_state = models.CharField(
        max_length=20,
        choices=SupportState.choices,
        default=SupportState.UNKNOWN,
    )
    auto_updates_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ("-id",)

    def clean(self):
        if self.version and self.version.family_id != self.family_id:
            raise ValidationError({"version": "Selected OS version must belong to selected family."})

    def __str__(self) -> str:
        if self.version:
            return f"{self.family.name} {self.version.version}"
        return self.family.name


class Network(models.Model):
    name = models.CharField(max_length=120, unique=True)
    vlan_id = models.PositiveIntegerField(null=True, blank=True)
    cidr = models.CharField(max_length=43)
    gateway = models.GenericIPAddressField(protocol="IPv4", null=True, blank=True)
    dhcp_enabled = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    def clean(self):
        try:
            network = ipaddress.IPv4Network(self.cidr, strict=False)
        except ValueError as error:
            raise ValidationError({"cidr": "Invalid IPv4 CIDR."}) from error

        self.cidr = str(network)

        if self.gateway:
            gateway = ipaddress.IPv4Address(self.gateway)
            if gateway not in network:
                raise ValidationError({"gateway": "Gateway must be inside the network CIDR."})

    def __str__(self) -> str:
        return f"{self.name} ({self.cidr})"


class NetworkInterface(TimeStampedModel):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="interfaces")
    port = models.ForeignKey(
        "Port",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="port_interfaces",
    )
    identifier = models.CharField(max_length=120)
    mac_address = models.CharField(
        max_length=17,
        blank=True,
        null=True,
        unique=True,
        validators=[validate_mac],
    )
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["asset", "identifier"], name="uniq_asset_interface_identifier")
        ]

    def clean(self):
        if self.mac_address:
            self.mac_address = normalize_mac(self.mac_address)
        if self.port_id and self.port.asset_id != self.asset_id:
            raise ValidationError({"port": "Interface port must belong to the same asset."})

    def __str__(self) -> str:
        return f"{self.asset.name}:{self.identifier}"


class IPAddress(TimeStampedModel):
    class Status(models.TextChoices):
        STATIC = "STATIC", "Static"
        DHCP_RESERVED = "DHCP_RESERVED", "DHCP Reserved"
        DHCP_DYNAMIC = "DHCP_DYNAMIC", "DHCP Dynamic"
        DEPRECATED = "DEPRECATED", "Deprecated"

    network = models.ForeignKey(Network, on_delete=models.CASCADE, related_name="ip_addresses")
    address = models.GenericIPAddressField(protocol="IPv4")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.STATIC)
    assigned_interface = models.ForeignKey(
        NetworkInterface,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ip_addresses",
    )
    hostname = models.CharField(max_length=200, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["network", "address"], name="uniq_network_ip_address"),
            models.UniqueConstraint(
                fields=["network", "assigned_interface"],
                condition=Q(active=True, assigned_interface__isnull=False),
                name="uniq_active_ip_per_network_interface",
            ),
        ]

    def clean(self):
        errors = {}
        try:
            network = ipaddress.IPv4Network(self.network.cidr, strict=False)
        except ValueError as error:
            raise ValidationError({"network": "Network CIDR is invalid."}) from error

        ip_address = ipaddress.IPv4Address(self.address)
        if ip_address not in network:
            errors["address"] = "IP address must be inside selected network CIDR."

        if self.assigned_interface_id and self.active:
            duplicate = IPAddress.objects.filter(
                network=self.network,
                assigned_interface=self.assigned_interface,
                active=True,
            )
            if self.pk:
                duplicate = duplicate.exclude(pk=self.pk)
            if duplicate.exists():
                errors["assigned_interface"] = (
                    "Only one active IP per interface in the same network is allowed."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.hostname and self.assigned_interface_id:
            self.hostname = self.assigned_interface.asset.name
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.address} ({self.network.name})"


class Port(TimeStampedModel):
    class PortKind(models.TextChoices):
        RJ45 = "RJ45", "RJ45"
        SFP = "SFP", "SFP"
        WIFI = "WIFI", "WiFi"
        VIRTUAL = "VIRTUAL", "Virtual"
        OTHER = "OTHER", "Other"

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="ports")
    name = models.CharField(max_length=120)
    port_kind = models.CharField(max_length=20, choices=PortKind.choices, default=PortKind.RJ45)
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["asset", "name"], name="uniq_asset_port_name")]

    def __str__(self) -> str:
        return f"{self.asset.name}:{self.name}"


class GuestDevice(TimeStampedModel):
    description = models.TextField(blank=True)
    sponsor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sponsored_guest_devices",
    )
    groups = models.ManyToManyField(OrganizationalGroup, related_name="guest_devices", blank=True)
    mac_address = models.CharField(max_length=17, validators=[validate_mac])
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField()
    enabled = models.BooleanField(default=True)

    def clean(self):
        self.mac_address = normalize_mac(self.mac_address)
        if self.valid_until <= self.valid_from:
            raise ValidationError({"valid_until": "valid_until must be later than valid_from."})

    def __str__(self) -> str:
        return self.mac_address


@receiver(post_save, sender=Asset)
def ensure_default_asset_connectivity(sender, instance: Asset, created: bool, **_kwargs):
    if instance.asset_type != Asset.AssetType.COMPUTER or not created:
        return
    if getattr(instance, "_skip_default_connectivity", False):
        return

    with transaction.atomic():
        port, _ = Port.objects.get_or_create(
            asset=instance,
            name="LAN",
            defaults={"port_kind": Port.PortKind.RJ45},
        )
        if not port.active:
            port.active = True
            port.save(update_fields=["active", "updated_at"])

        interface, _ = NetworkInterface.objects.get_or_create(
            asset=instance,
            identifier="lan",
            defaults={"port": port},
        )
        if not interface.active:
            interface.active = True
            interface.save(update_fields=["active", "updated_at"])

        if interface.port_id is None:
            interface.port = port
            interface.save(update_fields=["port", "updated_at"])
