from django.contrib.auth import get_user_model
from django.test import TestCase

from inventory.models import Asset, Network, OrganizationalGroup

User = get_user_model()


class BulkUpdateTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin-bulk",
            email="admin-bulk@example.local",
            password="x",
        )
        self.member = User.objects.create_user(
            username="member-bulk",
            email="member-bulk@example.local",
            password="x",
        )
        self.owner = User.objects.create_user(
            username="owner-bulk",
            email="owner-bulk@example.local",
            password="x",
        )

        self.group_admin = OrganizationalGroup.objects.create(name="Admins")
        self.group_admin.admins.add(self.admin)

        self.group_member = OrganizationalGroup.objects.create(name="Members")
        self.group_member.members.add(self.member)

        self.asset_editable = Asset.objects.create(
            name="pc-bulk-1",
            owner=self.owner,
            asset_type=Asset.AssetType.COMPUTER,
            status=Asset.Status.ACTIVE,
        )
        self.asset_editable.groups.add(self.group_admin)

        self.asset_forbidden = Asset.objects.create(
            name="pc-bulk-2",
            owner=self.owner,
            asset_type=Asset.AssetType.COMPUTER,
            status=Asset.Status.ACTIVE,
        )
        self.asset_forbidden.groups.add(self.group_member)
        self.network = Network.objects.create(name="bulk-net", cidr="10.88.0.0/24")

    def test_bulk_update_reports_errors_per_row(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            "/api/assets/bulk_update/",
            data={
                "rows": [
                    {"id": self.asset_editable.id, "status": Asset.Status.RETIRED},
                    {"id": self.asset_forbidden.id, "status": Asset.Status.RETIRED},
                    {"id": 999999, "status": Asset.Status.RETIRED},
                ]
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 207)
        results = response.json()["results"]
        self.assertEqual(results[0]["success"], True)
        self.assertEqual(results[1]["success"], False)
        self.assertEqual(results[2]["success"], False)

        self.asset_editable.refresh_from_db()
        self.asset_forbidden.refresh_from_db()
        self.assertEqual(self.asset_editable.status, Asset.Status.RETIRED)
        self.assertEqual(self.asset_forbidden.status, Asset.Status.ACTIVE)

    def test_interface_bulk_update_reports_errors_per_row(self):
        editable_interface = self.asset_editable.interfaces.get(identifier="lan")
        forbidden_interface = self.asset_forbidden.interfaces.get(identifier="lan")

        self.client.force_login(self.admin)
        response = self.client.post(
            "/api/interfaces/bulk_update/",
            data={
                "rows": [
                    {
                        "id": editable_interface.id,
                        "mac_address": "aa:bb:cc:dd:ee:71",
                        "network": self.network.id,
                        "address": "10.88.0.11",
                        "ip_status": "STATIC",
                    },
                    {
                        "id": forbidden_interface.id,
                        "mac_address": "aa:bb:cc:dd:ee:72",
                    },
                    {"id": 999999, "mac_address": "aa:bb:cc:dd:ee:73"},
                ]
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 207)
        results = response.json()["results"]
        self.assertEqual(results[0]["success"], True)
        self.assertEqual(results[1]["success"], False)
        self.assertEqual(results[2]["success"], False)

        editable_interface.refresh_from_db()
        forbidden_interface.refresh_from_db()
        self.assertEqual(editable_interface.mac_address, "aa:bb:cc:dd:ee:71")
        self.assertEqual(forbidden_interface.mac_address, None)
