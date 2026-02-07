from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import (
    Asset,
    AssetOS,
    IPAddress,
    Network,
    NetworkInterface,
    OrganizationalGroup,
    OSFamily,
    OSVersion,
    Port,
)

User = get_user_model()


def _get_primary_os(asset):
    if hasattr(asset, "_prefetched_objects_cache") and "os_entries" in asset._prefetched_objects_cache:
        entries = asset._prefetched_objects_cache["os_entries"]
        return entries[0] if entries else None
    return asset.os_entries.select_related("family", "version").order_by("-id").first()


def _raise_drf_validation(error: DjangoValidationError):
    raise serializers.ValidationError(error.message_dict if hasattr(error, "message_dict") else error.messages)


class UserLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name")


class ApiLoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=False)
    email = serializers.EmailField(required=False, allow_blank=False)
    password = serializers.CharField(required=True, write_only=True, allow_blank=False)

    def validate(self, attrs):
        if not attrs.get("username") and not attrs.get("email"):
            raise serializers.ValidationError({"username": "Provide either username or email."})
        return attrs


class GroupLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationalGroup
        fields = ("id", "name")


class GroupCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationalGroup
        fields = ("id", "name", "description", "default_vlan_id")
        read_only_fields = ("id",)

    def create(self, validated_data):
        group = OrganizationalGroup(**validated_data)
        try:
            group.full_clean()
        except DjangoValidationError as error:
            _raise_drf_validation(error)
        group.save()
        return group


class OSFamilyLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = OSFamily
        fields = ("id", "name", "vendor", "platform_type", "supports_domain_join")


class OSFamilyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OSFamily
        fields = ("id", "name", "vendor", "platform_type", "supports_domain_join")
        read_only_fields = ("id",)

    def create(self, validated_data):
        family = OSFamily(**validated_data)
        try:
            family.full_clean()
        except DjangoValidationError as error:
            _raise_drf_validation(error)
        family.save()
        return family


class OSVersionLookupSerializer(serializers.ModelSerializer):
    family_id = serializers.IntegerField(source="family.id", read_only=True)

    class Meta:
        model = OSVersion
        fields = (
            "id",
            "family_id",
            "version",
            "codename",
            "release_date",
            "end_of_support_date",
            "is_lts",
            "kernel_version",
        )


class AssetOSNestedSerializer(serializers.ModelSerializer):
    family = OSFamilyLookupSerializer(read_only=True)
    version = OSVersionLookupSerializer(read_only=True)

    class Meta:
        model = AssetOS
        fields = (
            "id",
            "family",
            "version",
            "patch_level",
            "installed_on",
            "support_state",
            "auto_updates_enabled",
        )


class NetworkLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Network
        fields = ("id", "name", "cidr", "vlan_id")


class PortLookupSerializer(serializers.ModelSerializer):
    asset_id = serializers.IntegerField(source="asset.id", read_only=True)
    asset_name = serializers.CharField(source="asset.name", read_only=True)

    class Meta:
        model = Port
        fields = (
            "id",
            "asset_id",
            "asset_name",
            "name",
            "port_kind",
            "active",
        )


class IPAddressNestedSerializer(serializers.ModelSerializer):
    network = NetworkLookupSerializer(read_only=True)

    class Meta:
        model = IPAddress
        fields = ("id", "network", "address", "status", "hostname", "active")


class InterfaceNestedSerializer(serializers.ModelSerializer):
    ips = serializers.SerializerMethodField()

    class Meta:
        model = NetworkInterface
        fields = (
            "id",
            "identifier",
            "mac_address",
            "active",
            "notes",
            "ips",
        )

    def get_ips(self, obj):
        ips = obj.ip_addresses.select_related("network").order_by("-active", "network__name", "id")
        return IPAddressNestedSerializer(ips, many=True).data


class PortNestedSerializer(serializers.ModelSerializer):
    interfaces = serializers.SerializerMethodField()

    class Meta:
        model = Port
        fields = ("id", "name", "port_kind", "active", "notes", "interfaces")

    def get_interfaces(self, obj):
        interfaces = obj.port_interfaces.order_by("identifier", "id")
        return InterfaceNestedSerializer(interfaces, many=True).data


class NetworkInterfaceListSerializer(serializers.ModelSerializer):
    asset_id = serializers.IntegerField(source="asset.id", read_only=True)
    asset_name = serializers.CharField(source="asset.name", read_only=True)
    port_name = serializers.SerializerMethodField()
    port_kind = serializers.SerializerMethodField()
    active_ip = serializers.SerializerMethodField()
    ip_history = serializers.SerializerMethodField()

    class Meta:
        model = NetworkInterface
        fields = (
            "id",
            "asset_id",
            "asset_name",
            "port",
            "port_name",
            "port_kind",
            "identifier",
            "mac_address",
            "active",
            "notes",
            "active_ip",
            "ip_history",
        )

    def get_port_name(self, obj):
        return obj.port.name if obj.port_id else None

    def get_port_kind(self, obj):
        return obj.port.port_kind if obj.port_id else None

    def get_active_ip(self, obj):
        active_ip = obj.ip_addresses.filter(active=True).select_related("network").order_by("id").first()
        if not active_ip:
            return None
        return {
            "id": active_ip.id,
            "address": active_ip.address,
            "status": active_ip.status,
            "hostname": active_ip.hostname,
            "network": {
                "id": active_ip.network_id,
                "name": active_ip.network.name,
                "cidr": active_ip.network.cidr,
            },
        }

    def get_ip_history(self, obj):
        return IPAddressNestedSerializer(
            obj.ip_addresses.select_related("network").order_by("-active", "-created_at", "id"),
            many=True,
        ).data


class NetworkInterfaceUpdateSerializer(serializers.ModelSerializer):
    port = serializers.PrimaryKeyRelatedField(queryset=Port.objects.all(), allow_null=True, required=False)
    network = serializers.PrimaryKeyRelatedField(
        queryset=Network.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    address = serializers.IPAddressField(write_only=True, required=False, allow_null=True)
    ip_status = serializers.ChoiceField(
        write_only=True,
        required=False,
        choices=IPAddress.Status.choices,
    )
    hostname = serializers.CharField(write_only=True, required=False, allow_blank=True)
    clear_ip = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = NetworkInterface
        fields = (
            "identifier",
            "mac_address",
            "port",
            "notes",
            "active",
            "network",
            "address",
            "ip_status",
            "hostname",
            "clear_ip",
        )

    def validate(self, attrs):
        instance = self.instance
        port = attrs.get("port", serializers.empty)
        if port is not serializers.empty and port is not None and instance and port.asset_id != instance.asset_id:
            raise serializers.ValidationError({"port": "Selected port must belong to the same asset."})

        clear_ip = attrs.get("clear_ip", False)
        has_network = "network" in attrs and attrs.get("network") is not None
        has_address = "address" in attrs and attrs.get("address") not in (None, "")
        ip_keys = {"network", "address", "ip_status", "hostname", "clear_ip"}
        has_ip_change = any(key in attrs for key in ip_keys)

        if has_ip_change and not clear_ip and not (has_network and has_address):
            raise serializers.ValidationError(
                {"address": "network and address must be provided together when updating active IP."}
            )

        return attrs

    def update(self, instance, validated_data):
        network = validated_data.pop("network", serializers.empty)
        address = validated_data.pop("address", serializers.empty)
        ip_status = validated_data.pop("ip_status", serializers.empty)
        hostname = validated_data.pop("hostname", serializers.empty)
        clear_ip = validated_data.pop("clear_ip", False)

        for key, value in validated_data.items():
            setattr(instance, key, value)

        try:
            instance.full_clean()
        except DjangoValidationError as error:
            _raise_drf_validation(error)
        instance.save()

        if clear_ip:
            active_ips = instance.ip_addresses.filter(active=True)
            if network is not serializers.empty and network is not None:
                active_ips = active_ips.filter(network=network)
            active_ips.update(active=False)
            return instance

        if network is serializers.empty or address in (serializers.empty, None, ""):
            return instance

        current_ip = instance.ip_addresses.filter(active=True, network=network).order_by("id").first()
        next_status = (
            ip_status
            if ip_status is not serializers.empty
            else (current_ip.status if current_ip else IPAddress.Status.STATIC)
        )
        next_hostname = (
            hostname
            if hostname is not serializers.empty
            else (current_ip.hostname if current_ip else "")
        )

        if current_ip and current_ip.address == address:
            current_ip.status = next_status
            current_ip.hostname = next_hostname
            try:
                current_ip.full_clean()
            except DjangoValidationError as error:
                _raise_drf_validation(error)
            current_ip.save()
            return instance

        if current_ip:
            current_ip.active = False
            current_ip.save(update_fields=["active", "updated_at"])

        ip_record = IPAddress(
            network=network,
            address=address,
            status=next_status,
            assigned_interface=instance,
            hostname=next_hostname,
            active=True,
        )
        try:
            ip_record.full_clean()
        except DjangoValidationError as error:
            _raise_drf_validation(error)
        ip_record.save()
        return instance


class NetworkInterfaceCreateSerializer(serializers.ModelSerializer):
    asset = serializers.PrimaryKeyRelatedField(queryset=Asset.objects.all())
    port = serializers.PrimaryKeyRelatedField(queryset=Port.objects.all(), allow_null=True, required=False)
    network = serializers.PrimaryKeyRelatedField(
        queryset=Network.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    address = serializers.IPAddressField(write_only=True, required=False, allow_null=True)
    ip_status = serializers.ChoiceField(
        write_only=True,
        required=False,
        choices=IPAddress.Status.choices,
        default=IPAddress.Status.STATIC,
    )
    hostname = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = NetworkInterface
        fields = (
            "asset",
            "identifier",
            "mac_address",
            "port",
            "notes",
            "active",
            "network",
            "address",
            "ip_status",
            "hostname",
        )

    def validate(self, attrs):
        asset = attrs["asset"]
        port = attrs.get("port")
        if port is not None and port.asset_id != asset.id:
            raise serializers.ValidationError({"port": "Selected port must belong to the same asset."})

        has_network = attrs.get("network") is not None
        has_address = attrs.get("address") not in (None, "")
        if has_network != has_address:
            raise serializers.ValidationError(
                {"address": "network and address must be provided together when setting active IP."}
            )

        user = getattr(self.context.get("request"), "user", None)
        if user and not user.is_superuser:
            if not asset.groups.filter(id__in=user.asset_admin_groups.values("id")).exists():
                raise serializers.ValidationError(
                    {"asset": "Missing permission to create interfaces for this asset."}
                )
        return attrs

    def create(self, validated_data):
        network = validated_data.pop("network", None)
        address = validated_data.pop("address", None)
        ip_status = validated_data.pop("ip_status", IPAddress.Status.STATIC)
        hostname = validated_data.pop("hostname", "")
        interface = NetworkInterface(**validated_data)
        try:
            interface.full_clean()
        except DjangoValidationError as error:
            _raise_drf_validation(error)
        interface.save()

        if network and address:
            ip_record = IPAddress(
                network=network,
                address=address,
                status=ip_status,
                assigned_interface=interface,
                hostname=hostname,
                active=True,
            )
            try:
                ip_record.full_clean()
            except DjangoValidationError as error:
                _raise_drf_validation(error)
            ip_record.save()
        return interface


class PortCreateSerializer(serializers.ModelSerializer):
    asset = serializers.PrimaryKeyRelatedField(queryset=Asset.objects.all())

    class Meta:
        model = Port
        fields = ("asset", "name", "port_kind", "notes", "active")

    def validate(self, attrs):
        asset = attrs["asset"]
        user = getattr(self.context.get("request"), "user", None)
        if user and not user.is_superuser:
            if not asset.groups.filter(id__in=user.asset_admin_groups.values("id")).exists():
                raise serializers.ValidationError({"asset": "Missing permission to create ports for this asset."})

        duplicate = Port.objects.filter(asset=asset, name=attrs["name"])
        if duplicate.exists():
            raise serializers.ValidationError({"name": "Port name must be unique per asset."})
        return attrs

    def create(self, validated_data):
        port = Port(**validated_data)
        try:
            port.full_clean()
        except DjangoValidationError as error:
            _raise_drf_validation(error)
        port.save()
        return port


class AssetPortInterfaceCreateSerializer(serializers.Serializer):
    port_name = serializers.CharField(required=True, allow_blank=False, max_length=120)
    port_kind = serializers.ChoiceField(required=False, choices=Port.PortKind.choices, default=Port.PortKind.RJ45)
    port_notes = serializers.CharField(required=False, allow_blank=True, default="")
    port_active = serializers.BooleanField(required=False, default=True)

    interface_identifier = serializers.CharField(required=True, allow_blank=False, max_length=120)
    interface_mac_address = serializers.CharField(required=False, allow_blank=True, allow_null=True, default="")
    interface_notes = serializers.CharField(required=False, allow_blank=True, default="")
    interface_active = serializers.BooleanField(required=False, default=True)

    def validate_port_name(self, value):
        return value.strip()

    def validate_interface_identifier(self, value):
        return value.strip()


class PortUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Port
        fields = ("name", "port_kind", "notes", "active")

    def validate(self, attrs):
        instance = self.instance
        if not instance:
            return attrs
        name = attrs.get("name", instance.name)
        duplicate = Port.objects.filter(asset=instance.asset, name=name).exclude(pk=instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError({"name": "Port name must be unique per asset."})
        return attrs

    def update(self, instance, validated_data):
        for key, value in validated_data.items():
            setattr(instance, key, value)
        try:
            instance.full_clean()
        except DjangoValidationError as error:
            _raise_drf_validation(error)
        instance.save()
        return instance


class AssetUpdateSerializer(serializers.ModelSerializer):
    groups = serializers.PrimaryKeyRelatedField(
        queryset=OrganizationalGroup.objects.all(),
        many=True,
        required=False,
    )
    owner = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    os_family = serializers.PrimaryKeyRelatedField(
        queryset=OSFamily.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    os_version = serializers.PrimaryKeyRelatedField(
        queryset=OSVersion.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = Asset
        fields = (
            "name",
            "asset_type",
            "asset_tag",
            "serial_number",
            "manufacturer",
            "model",
            "owner",
            "groups",
            "status",
            "notes",
            "metadata",
            "os_family",
            "os_version",
        )

    def validate(self, attrs):
        os_family = attrs.get("os_family", serializers.empty)
        os_version = attrs.get("os_version", serializers.empty)

        if os_version not in (serializers.empty, None):
            if os_family in (serializers.empty, None):
                existing = _get_primary_os(self.instance)
                if existing is None:
                    raise serializers.ValidationError(
                        {"os_family": "os_family is required when setting os_version."}
                    )
                os_family = existing.family
                attrs["os_family"] = os_family
            if os_version.family_id != os_family.id:
                raise serializers.ValidationError(
                    {"os_version": "Selected OS version must belong to selected family."}
                )

        return attrs

    def update(self, instance, validated_data):
        os_family = validated_data.pop("os_family", serializers.empty)
        os_version = validated_data.pop("os_version", serializers.empty)
        groups = validated_data.pop("groups", serializers.empty)

        for key, value in validated_data.items():
            setattr(instance, key, value)

        try:
            instance.full_clean()
        except DjangoValidationError as error:
            _raise_drf_validation(error)
        instance.save()

        if groups is not serializers.empty:
            instance.groups.set(groups)

        if os_family is not serializers.empty or os_version is not serializers.empty:
            if os_family is None:
                AssetOS.objects.filter(asset=instance).delete()
            else:
                os_record = _get_primary_os(instance)
                if os_record is None:
                    os_record = AssetOS(asset=instance, family=os_family)
                os_record.family = os_family
                os_record.version = None if os_version in (serializers.empty, None) else os_version
                try:
                    os_record.full_clean()
                except DjangoValidationError as error:
                    _raise_drf_validation(error)
                os_record.save()

        return instance


class AssetCreateSerializer(serializers.ModelSerializer):
    groups = serializers.PrimaryKeyRelatedField(
        queryset=OrganizationalGroup.objects.all(),
        many=True,
        required=False,
    )
    owner = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    os_family = serializers.PrimaryKeyRelatedField(
        queryset=OSFamily.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    os_version = serializers.PrimaryKeyRelatedField(
        queryset=OSVersion.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = Asset
        fields = (
            "name",
            "asset_type",
            "asset_tag",
            "serial_number",
            "manufacturer",
            "model",
            "owner",
            "groups",
            "status",
            "notes",
            "metadata",
            "os_family",
            "os_version",
        )

    def validate(self, attrs):
        user = getattr(self.context.get("request"), "user", None)
        if user and not user.is_superuser and not user.asset_admin_groups.exists():
            raise serializers.ValidationError({"detail": "Missing permission to create assets."})

        groups = attrs.get("groups", [])
        if user and not user.is_superuser:
            if not groups:
                raise serializers.ValidationError({"groups": "At least one group is required for new assets."})
            allowed_ids = set(user.asset_admin_groups.values_list("id", flat=True))
            if any(group.id not in allowed_ids for group in groups):
                raise serializers.ValidationError({"groups": "Group assignment is outside your managed groups."})

        os_family = attrs.get("os_family")
        os_version = attrs.get("os_version")
        if os_version is not None and os_family is None:
            raise serializers.ValidationError({"os_family": "os_family is required when setting os_version."})
        if os_version is not None and os_version.family_id != os_family.id:
            raise serializers.ValidationError({"os_version": "Selected OS version must belong to selected family."})
        return attrs

    def create(self, validated_data):
        user = getattr(self.context.get("request"), "user", None)
        os_family = validated_data.pop("os_family", None)
        os_version = validated_data.pop("os_version", None)
        groups = validated_data.pop("groups", [])
        asset = Asset(**validated_data)
        asset._skip_default_connectivity = True
        try:
            asset.full_clean()
        except DjangoValidationError as error:
            _raise_drf_validation(error)
        asset.save()

        if groups:
            asset.groups.set(groups)

        if os_family is not None:
            os_record = AssetOS(asset=asset, family=os_family, version=os_version)
            try:
                os_record.full_clean()
            except DjangoValidationError as error:
                _raise_drf_validation(error)
            os_record.save()
        return asset


class AssetListSerializer(serializers.ModelSerializer):
    owner = UserLookupSerializer(read_only=True)
    groups = GroupLookupSerializer(many=True, read_only=True)
    os_family = serializers.SerializerMethodField()
    os_version = serializers.SerializerMethodField()
    os_features = serializers.SerializerMethodField()
    os_entries = serializers.SerializerMethodField()
    ports = serializers.SerializerMethodField()
    unassigned_interfaces = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = (
            "id",
            "name",
            "asset_type",
            "asset_tag",
            "serial_number",
            "manufacturer",
            "model",
            "owner",
            "groups",
            "status",
            "notes",
            "metadata",
            "os_family",
            "os_version",
            "os_features",
            "os_entries",
            "ports",
            "unassigned_interfaces",
            "created_at",
            "updated_at",
        )

    def get_os_family(self, obj):
        os_record = _get_primary_os(obj)
        if os_record is None:
            return None
        return {"id": os_record.family_id, "name": os_record.family.name}

    def get_os_version(self, obj):
        os_record = _get_primary_os(obj)
        if os_record is None or os_record.version is None:
            return None
        return {"id": os_record.version_id, "version": os_record.version.version}

    def get_os_features(self, obj):
        os_record = _get_primary_os(obj)
        if os_record is None:
            return None
        return {
            "patch_level": os_record.patch_level,
            "installed_on": os_record.installed_on,
            "support_state": os_record.support_state,
            "auto_updates_enabled": os_record.auto_updates_enabled,
        }

    def get_os_entries(self, obj):
        entries = obj.os_entries.select_related("family", "version").order_by("-id")
        return AssetOSNestedSerializer(entries, many=True).data

    def get_ports(self, obj):
        ports = obj.ports.order_by("name", "id")
        return PortNestedSerializer(ports, many=True).data

    def get_unassigned_interfaces(self, obj):
        interfaces = obj.interfaces.filter(port__isnull=True).order_by("identifier", "id")
        return InterfaceNestedSerializer(interfaces, many=True).data


class BulkAssetRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    owner = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    status = serializers.ChoiceField(choices=Asset.Status.choices, required=False)
    groups = serializers.PrimaryKeyRelatedField(
        queryset=OrganizationalGroup.objects.all(),
        many=True,
        required=False,
    )
    os_family = serializers.PrimaryKeyRelatedField(queryset=OSFamily.objects.all(), required=False, allow_null=True)
    os_version = serializers.PrimaryKeyRelatedField(queryset=OSVersion.objects.all(), required=False, allow_null=True)


class BulkInterfaceRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    identifier = serializers.CharField(required=False)
    mac_address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    port = serializers.PrimaryKeyRelatedField(queryset=Port.objects.all(), required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    active = serializers.BooleanField(required=False)

    network = serializers.PrimaryKeyRelatedField(
        queryset=Network.objects.all(),
        required=False,
        allow_null=True,
    )
    address = serializers.IPAddressField(required=False, allow_null=True)
    ip_status = serializers.ChoiceField(
        required=False,
        choices=IPAddress.Status.choices,
    )
    hostname = serializers.CharField(required=False, allow_blank=True)
    clear_ip = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        clear_ip = attrs.get("clear_ip", False)
        has_network = "network" in attrs and attrs.get("network") is not None
        has_address = "address" in attrs and attrs.get("address") not in (None, "")
        ip_keys = {"network", "address", "ip_status", "hostname", "clear_ip"}
        has_ip_change = any(key in attrs for key in ip_keys)

        if has_ip_change and not clear_ip and not (has_network and has_address):
            raise serializers.ValidationError(
                {"address": "network and address must be provided together when updating active IP."}
            )

        return attrs
