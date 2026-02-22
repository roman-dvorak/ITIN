from __future__ import annotations

import ipaddress
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone
from simple_history.models import HistoricalRecords

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


class Location(TimeStampedModel):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    path_cache = models.CharField(max_length=2000, blank=True, default="", db_index=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    groups = models.ManyToManyField(OrganizationalGroup, related_name="locations", blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["parent", "name"], name="uniq_location_name_per_parent"),
            models.UniqueConstraint(fields=["parent", "slug"], name="uniq_location_slug_per_parent"),
        ]
        ordering = ("name", "id")

    def clean(self):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.slug:
            raise ValidationError({"slug": "Slug cannot be empty."})
        if self.parent_id and self.parent_id == self.id:
            raise ValidationError({"parent": "Location cannot be parent of itself."})

        current = self.parent
        while current:
            if self.id and current.id == self.id:
                raise ValidationError({"parent": "Location hierarchy cannot contain cycles."})
            current = current.parent

    def ancestor_chain(self):
        chain = []
        current = self
        while current:
            chain.append(current)
            current = current.parent
        return list(reversed(chain))

    def _compute_path_cache(self):
        if not self.parent_id:
            return self.slug
        parent_path = (
            Location.objects.filter(pk=self.parent_id).values_list("path_cache", flat=True).first() or ""
        )
        if parent_path:
            return f"{parent_path}/{self.slug}"
        parent = Location.objects.select_related("parent").get(pk=self.parent_id)
        return f"{parent.path}/{self.slug}"

    def _rebuild_descendant_paths(self):
        children = list(Location.objects.filter(parent_id=self.id).only("id", "slug", "path_cache"))
        for child in children:
            new_path = f"{self.path_cache}/{child.slug}" if self.path_cache else child.slug
            if child.path_cache != new_path:
                Location.objects.filter(pk=child.id).update(path_cache=new_path)
                child.path_cache = new_path
            child._rebuild_descendant_paths()

    @property
    def path(self):
        if self.path_cache:
            return self.path_cache
        return "/".join(item.slug for item in self.ancestor_chain())

    @property
    def path_label(self):
        return self.path

    def save(self, *args, **kwargs):
        old_parent_id = None
        old_slug = None
        if self.pk:
            old_parent_id, old_slug = (
                Location.objects.filter(pk=self.pk).values_list("parent_id", "slug").first() or (None, None)
            )
        super().save(*args, **kwargs)
        new_path = self._compute_path_cache()
        path_changed = new_path != self.path_cache
        if path_changed:
            Location.objects.filter(pk=self.pk).update(path_cache=new_path)
            self.path_cache = new_path
        if path_changed or old_parent_id != self.parent_id or old_slug != self.slug:
            self._rebuild_descendant_paths()

    def get_absolute_url(self):
        return reverse("inventory:location-detail", args=[self.pk, self.slug])

    def __str__(self) -> str:
        return self.path_label


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
        SPARE = "SPARE", "Spare"
        RETIRED = "RETIRED", "Retired"
        DISCARDED = "DISCARDED", "Discarded"
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
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    commissioning_date = models.DateField(null=True, blank=True, verbose_name="Commissioning date")
    last_seen = models.DateTimeField(null=True, blank=True, verbose_name="Last seen")
    tags = models.ManyToManyField("AssetTag", related_name="assets", blank=True)
    lifetime_override_months = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Lifetime override (months)"
    )

    history = HistoricalRecords()
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
        return self.os_entries.select_related("family").order_by("-id").first()

    @property
    def effective_lifetime_months(self):
        if self.lifetime_override_months:
            return self.lifetime_override_months
        try:
            return AssetTypeLifetime.objects.get(asset_type=self.asset_type).planned_lifetime_months
        except AssetTypeLifetime.DoesNotExist:
            return None

    @property
    def end_of_lifetime(self):
        months = self.effective_lifetime_months
        if months and self.commissioning_date:
            from dateutil.relativedelta import relativedelta
            return self.commissioning_date + relativedelta(months=months)
        return None

    @property
    def current_approval_status(self):
        latest = self.approval_requests.order_by("-requested_at").first()
        if latest:
            return latest.status
        return None


class AssetTag(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class AssetTypeLifetime(models.Model):
    asset_type = models.CharField(max_length=20, choices=Asset.AssetType.choices, unique=True)
    planned_lifetime_months = models.PositiveIntegerField(help_text="Default lifetime in months")

    class Meta:
        ordering = ("asset_type",)

    def __str__(self) -> str:
        return f"{self.get_asset_type_display()} ({self.planned_lifetime_months} months)"


class OSFamily(models.Model):
    class FamilyType(models.TextChoices):
        LINUX = "linux", "Linux"
        WINDOWS = "windows", "Windows"
        NAS_OS = "nas-os", "NAS OS"
        NETWORK_OS = "network-os", "Network OS"
        ANDROID = "android", "Android"
        MACOS = "macos", "macOS"
        OTHER = "other", "Other"

    class SupportStatus(models.TextChoices):
        SUPPORTED = "SUPPORTED", "Supported"
        UNSUPPORTED = "UNSUPPORTED", "Unsupported"

    family = models.CharField(max_length=20, choices=FamilyType.choices, default=FamilyType.OTHER)
    name = models.CharField(max_length=120)
    flavor = models.CharField(max_length=120, blank=True, null=True)
    support_status = models.CharField(
        max_length=20,
        choices=SupportStatus.choices,
        default=SupportStatus.SUPPORTED,
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["family", "name", "flavor"], name="uniq_os_catalog_item"),
        ]
        ordering = ("family", "name", "flavor", "id")

    @property
    def name_flavor(self) -> str:
        if self.flavor:
            return f"{self.name} - {self.flavor}"
        return self.name

    def __str__(self) -> str:
        return f"{self.get_family_display()} / {self.name_flavor}"


class AssetOS(models.Model):
    class SupportState(models.TextChoices):
        UNKNOWN = "UNKNOWN", "Unknown"
        SUPPORTED = "SUPPORTED", "Supported"
        EXTENDED = "EXTENDED", "Extended"
        EOL = "EOL", "End of life"

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="os_entries")
    family = models.ForeignKey(OSFamily, on_delete=models.PROTECT)
    version = models.CharField(max_length=120, blank=True)
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

    def __str__(self) -> str:
        if self.version:
            return f"{self.family.name_flavor} {self.version}"
        return self.family.name_flavor


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
    class ApprovalStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        DISABLED = "DISABLED", "Disabled"

    device_name = models.CharField(max_length=200, blank=True)
    owner_name = models.CharField(max_length=200, blank=True)
    owner_email = models.EmailField(blank=True)
    description = models.TextField(blank=True)
    network = models.ForeignKey(
        "Network",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="guest_access_devices",
    )
    sponsor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sponsored_guest_devices",
    )
    groups = models.ManyToManyField(OrganizationalGroup, related_name="guest_devices", blank=True)
    mac_address = models.CharField(max_length=17, validators=[validate_mac])
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField()
    approval_status = models.CharField(
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.APPROVED,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_guest_devices",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_reason = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)

    def clean(self):
        self.mac_address = normalize_mac(self.mac_address)
        if self.valid_until <= self.valid_from:
            raise ValidationError({"valid_until": "valid_until must be later than valid_from."})

    def __str__(self) -> str:
        if self.device_name:
            return f"{self.device_name} ({self.mac_address})"
        return self.mac_address


User = get_user_model()


class UserProfile(models.Model):
    """Extended user profile with metadata from external sources."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        primary_key=True,
    )
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return f"Profile for {self.user.username}"


class NetworkApprovalRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        REVOKED = "REVOKED", "Revoked"

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="approval_requests")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="submitted_approval_requests",
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_approval_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    class Meta:
        ordering = ("-requested_at",)

    def __str__(self) -> str:
        return f"Approval #{self.pk} for {self.asset} ({self.status})"


class TaskRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    task_name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    stdout = models.TextField(blank=True)
    result_data = models.JSONField(default=dict, blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ("-started_at",)

    def __str__(self) -> str:
        return f"{self.task_name} ({self.status}) @ {self.started_at}"


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


@receiver(post_save, sender=NetworkInterface)
def revoke_approval_on_interface_change(sender, instance: NetworkInterface, created: bool, **_kwargs):
    """Auto-revoke the latest APPROVED approval request when an interface changes."""
    if created:
        return
    latest_approved = (
        NetworkApprovalRequest.objects.filter(
            asset=instance.asset,
            status=NetworkApprovalRequest.Status.APPROVED,
        )
        .order_by("-requested_at")
        .first()
    )
    if latest_approved:
        latest_approved.status = NetworkApprovalRequest.Status.REVOKED
        latest_approved.save(update_fields=["status", "updated_at"])
