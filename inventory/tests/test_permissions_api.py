from django.contrib.auth import get_user_model
from django.test import TestCase

from inventory.models import Asset, Network, OrganizationalGroup

User = get_user_model()


class AssetPermissionApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin", email="admin@example.local", password="x")
        self.member = User.objects.create_user(username="member", email="member@example.local", password="x")
        self.outsider = User.objects.create_user(username="outsider", email="outsider@example.local", password="x")
        self.owner = User.objects.create_user(username="owner", email="owner@example.local", password="x")

        self.group = OrganizationalGroup.objects.create(name="IT")
        self.group.admins.add(self.admin)
        self.group.members.add(self.member)

        self.asset = Asset.objects.create(name="pc-api-1", owner=self.owner, asset_type=Asset.AssetType.COMPUTER)
        self.asset.groups.add(self.group)
        self.interface = self.asset.interfaces.get(identifier="lan")
        self.network = Network.objects.create(name="corp-api", cidr="10.77.0.0/24")

    def test_member_cannot_see_or_patch_asset(self):
        self.client.force_login(self.member)
        response = self.client.get("/api/assets/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 0)

        patch_response = self.client.patch(
            f"/api/assets/{self.asset.id}/",
            data={"status": Asset.Status.RETIRED},
            content_type="application/json",
        )
        self.assertEqual(patch_response.status_code, 404)

    def test_owner_can_read_but_cannot_patch_asset(self):
        self.client.force_login(self.owner)
        response = self.client.get("/api/assets/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

        patch_response = self.client.patch(
            f"/api/assets/{self.asset.id}/",
            data={"status": Asset.Status.RETIRED},
            content_type="application/json",
        )
        self.assertEqual(patch_response.status_code, 403)

    def test_group_admin_can_patch(self):
        self.client.force_login(self.admin)
        patch_response = self.client.patch(
            f"/api/assets/{self.asset.id}/",
            data={"status": Asset.Status.STORED},
            content_type="application/json",
        )
        self.assertEqual(patch_response.status_code, 200)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, Asset.Status.STORED)

    def test_outsider_cannot_see_asset(self):
        self.client.force_login(self.outsider)
        response = self.client.get("/api/assets/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_group_admin_can_patch_interface(self):
        self.client.force_login(self.admin)
        patch_response = self.client.patch(
            f"/api/interfaces/{self.interface.id}/",
            data={
                "mac_address": "aa:bb:cc:dd:ee:99",
                "network": self.network.id,
                "address": "10.77.0.11",
                "ip_status": "STATIC",
            },
            content_type="application/json",
        )
        self.assertEqual(patch_response.status_code, 200)
        self.interface.refresh_from_db()
        self.assertEqual(self.interface.mac_address, "aa:bb:cc:dd:ee:99")
        self.assertEqual(self.interface.ip_addresses.filter(active=True).count(), 1)

    def test_member_cannot_patch_interface(self):
        self.client.force_login(self.member)
        patch_response = self.client.patch(
            f"/api/interfaces/{self.interface.id}/",
            data={"mac_address": "aa:bb:cc:dd:ee:88"},
            content_type="application/json",
        )
        self.assertEqual(patch_response.status_code, 404)
