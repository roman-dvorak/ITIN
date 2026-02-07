import json
import tempfile
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from inventory.models import Asset, GuestDevice, IPAddress, Network, OrganizationalGroup

User = get_user_model()


class ExportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="owner-export",
            email="owner-export@example.local",
            password="x",
        )
        self.group = OrganizationalGroup.objects.create(name="Export Group", default_vlan_id=120)
        self.group.admins.add(self.user)

        self.asset = Asset.objects.create(name="pc-export", owner=self.user, asset_type=Asset.AssetType.COMPUTER)
        self.asset.groups.add(self.group)
        self.interface = self.asset.interfaces.get(identifier="lan")
        self.interface.mac_address = "aa:bb:cc:dd:ee:ff"
        self.interface.full_clean()
        self.interface.save()

        self.network = Network.objects.create(name="corp", cidr="10.20.30.0/24")
        ip = IPAddress(
            network=self.network,
            address="10.20.30.10",
            status=IPAddress.Status.STATIC,
            assigned_interface=self.interface,
            active=True,
        )
        ip.full_clean()
        ip.save()

        now = timezone.now()
        self.guest = GuestDevice.objects.create(
            sponsor=self.user,
            mac_address="11:22:33:44:55:66",
            valid_from=now,
            valid_until=now + timedelta(days=1),
            enabled=True,
        )
        self.guest.groups.add(self.group)

    def test_export_dhcp_contains_interfaces_and_guests(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "dhcp.json"
            call_command("export_dhcp", out=str(output))
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(len(data["interfaces"]), 1)
        self.assertEqual(data["interfaces"][0]["mac_address"], "aa:bb:cc:dd:ee:ff")
        self.assertEqual(data["interfaces"][0]["ips"][0]["address"], "10.20.30.10")
        self.assertEqual(len(data["guests"]), 1)
        self.assertEqual(data["guests"][0]["mac_address"], "11:22:33:44:55:66")

    def test_export_radius_contains_vlan_line(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "radius-authorize"
            call_command("export_radius", out=str(output))
            lines = output.read_text(encoding="utf-8")

        self.assertIn("AA-BB-CC-DD-EE-FF", lines)
        self.assertIn("11-22-33-44-55-66", lines)
        self.assertIn('Tunnel-Private-Group-Id := "120"', lines)
