from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from inventory.models import Asset, AssetOS, IPAddress, Network, NetworkInterface, OSFamily, OSVersion, Port

User = get_user_model()


class ModelRulesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", email="owner@example.local", password="x")

    def test_default_interface_and_port_are_auto_created_for_computer(self):
        asset = Asset.objects.create(name="pc-1", owner=self.user, asset_type=Asset.AssetType.COMPUTER)
        interface = NetworkInterface.objects.get(asset=asset, identifier="lan")
        port = Port.objects.get(asset=asset, name="LAN")
        self.assertEqual(interface.port_id, port.id)
        self.assertTrue(port.active)
        self.assertTrue(interface.active)
        self.assertEqual(port.port_kind, Port.PortKind.RJ45)

    def test_network_identity_has_single_source_of_truth(self):
        asset = Asset.objects.create(name="pc-1b", owner=self.user, asset_type=Asset.AssetType.COMPUTER)
        interface = NetworkInterface.objects.get(asset=asset, identifier="lan")
        self.assertEqual(interface.port.asset_id, asset.id)
        self.assertEqual(interface.port.name, "LAN")

    def test_os_family_version_uniqueness(self):
        family = OSFamily.objects.create(name="Windows 11 Enterprise")
        OSVersion.objects.create(family=family, version="23H2")
        with self.assertRaises(IntegrityError):
            OSVersion.objects.create(family=family, version="23H2")

    def test_asset_os_rejects_version_from_other_family(self):
        asset = Asset.objects.create(name="pc-2", owner=self.user, asset_type=Asset.AssetType.COMPUTER)
        family_a = OSFamily.objects.create(name="Windows 11 Enterprise")
        family_b = OSFamily.objects.create(name="Ubuntu")
        version_b = OSVersion.objects.create(family=family_b, version="24.04")

        assignment = AssetOS(asset=asset, family=family_a, version=version_b)
        with self.assertRaises(ValidationError):
            assignment.full_clean()

    def test_ip_must_be_within_network_cidr(self):
        network = Network.objects.create(name="office", cidr="192.168.1.0/24")
        asset = Asset.objects.create(name="pc-3", owner=self.user, asset_type=Asset.AssetType.COMPUTER)
        interface = asset.interfaces.get(identifier="lan")

        ip = IPAddress(
            network=network,
            address="10.0.0.5",
            assigned_interface=interface,
            status=IPAddress.Status.STATIC,
            active=True,
        )
        with self.assertRaises(ValidationError):
            ip.full_clean()

    def test_only_one_active_ip_per_network_interface(self):
        network = Network.objects.create(name="lan", cidr="10.10.0.0/24")
        asset = Asset.objects.create(name="pc-4", owner=self.user, asset_type=Asset.AssetType.COMPUTER)
        interface = asset.interfaces.get(identifier="lan")
        IPAddress.objects.create(
            network=network,
            address="10.10.0.11",
            assigned_interface=interface,
            status=IPAddress.Status.STATIC,
            active=True,
        )

        second = IPAddress(
            network=network,
            address="10.10.0.12",
            assigned_interface=interface,
            status=IPAddress.Status.DHCP_RESERVED,
            active=True,
        )
        with self.assertRaises(ValidationError):
            second.full_clean()
