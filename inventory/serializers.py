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


def _raise_drf_validation(error: DjangoValidationError):
    raise serializers.ValidationError(error.message_dict if hasattr(error, "message_dict") else error.messages)


class UserLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name")


class GroupLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationalGroup
        fields = ("id", "name")


class OSFamilyLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = OSFamily
        fields = ("id", "name", "vendor", "platform_type", "supports_domain_join")


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
    owner = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True), required=False)
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
                existing = getattr(self.instance, "asset_os", None)
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
                os_record, _ = AssetOS.objects.get_or_create(asset=instance, defaults={"family": os_family})
                os_record.family = os_family
                os_record.version = None if os_version in (serializers.empty, None) else os_version
                try:
                    os_record.full_clean()
                except DjangoValidationError as error:
                    _raise_drf_validation(error)
                os_record.save()

        return instance


class AssetListSerializer(serializers.ModelSerializer):
    owner = UserLookupSerializer(read_only=True)
    groups = GroupLookupSerializer(many=True, read_only=True)
    os_family = serializers.SerializerMethodField()
    os_version = serializers.SerializerMethodField()
    os_features = serializers.SerializerMethodField()
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
            "ports",
            "unassigned_interfaces",
            "created_at",
            "updated_at",
        )

    def get_os_family(self, obj):
        if not hasattr(obj, "asset_os"):
            return None
        return {"id": obj.asset_os.family_id, "name": obj.asset_os.family.name}

    def get_os_version(self, obj):
        if not hasattr(obj, "asset_os") or obj.asset_os.version is None:
            return None
        return {"id": obj.asset_os.version_id, "version": obj.asset_os.version.version}

    def get_os_features(self, obj):
        if not hasattr(obj, "asset_os"):
            return None
        return {
            "patch_level": obj.asset_os.patch_level,
            "installed_on": obj.asset_os.installed_on,
            "support_state": obj.asset_os.support_state,
            "auto_updates_enabled": obj.asset_os.auto_updates_enabled,
        }

    def get_ports(self, obj):
        ports = obj.ports.order_by("name", "id")
        return PortNestedSerializer(ports, many=True).data

    def get_unassigned_interfaces(self, obj):
        interfaces = obj.interfaces.filter(port__isnull=True).order_by("identifier", "id")
        return InterfaceNestedSerializer(interfaces, many=True).data


class BulkAssetRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    owner = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True), required=False)
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
