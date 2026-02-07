from django.contrib.auth import get_user_model
from django.test import TestCase

from inventory.models import Asset, AssetOS, NetworkInterface, OrganizationalGroup, OSFamily, OSVersion, Port

User = get_user_model()


class PageRoutingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="viewer", email="viewer@example.local", password="x")
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.owner = User.objects.create_user(
            username="owner-page",
            email="owner-page@example.local",
            password="x",
        )
        self.group = OrganizationalGroup.objects.create(name="Page Group")
        self.group.members.add(self.user)
        self.group.admins.add(self.user)
        self.asset = Asset.objects.create(name="page-asset-1", owner=self.owner, asset_type=Asset.AssetType.COMPUTER)
        self.asset.groups.add(self.group)
        self.owned_asset = Asset.objects.create(
            name="page-owned-asset",
            owner=self.user,
            asset_type=Asset.AssetType.COMPUTER,
        )
        self.hidden_asset = Asset.objects.create(
            name="page-hidden-asset",
            owner=self.owner,
            asset_type=Asset.AssetType.COMPUTER,
        )
        self.family = OSFamily.objects.create(name="Windows 11 Pro", vendor="Microsoft")
        self.version = OSVersion.objects.create(family=self.family, version="24H2")

    def test_home_contains_statistics_cards(self):
        self.client.force_login(self.user)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "Total Assets")
        self.assertContains(response, "viewer@example.local")
        self.assertNotContains(response, ">Admin<", html=False)

    def test_asset_list_is_available_on_asset_path(self):
        self.client.force_login(self.user)
        response = self.client.get("/asset/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assets")
        self.assertContains(response, self.asset.name)
        self.assertContains(response, self.owned_asset.name)
        self.assertNotContains(response, self.hidden_asset.name)
        self.assertNotContains(response, "Quick Add Computer")

    def test_asset_list_filters_by_query_and_status(self):
        self.client.force_login(self.user)
        response = self.client.get("/asset/?q=owned&status=ACTIVE")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.owned_asset.name)
        self.assertNotContains(response, self.asset.name)

    def test_asset_list_filters_by_multiple_groups(self):
        second_group = OrganizationalGroup.objects.create(name="Second Page Group")
        second_group.members.add(self.user)
        second_group.admins.add(self.user)
        second_asset = Asset.objects.create(
            name="page-second-group-asset",
            owner=self.owner,
            asset_type=Asset.AssetType.COMPUTER,
        )
        second_asset.groups.add(second_group)

        self.client.force_login(self.user)
        response = self.client.get("/asset/", data={"group": [str(self.group.id), str(second_group.id)]})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.asset.name)
        self.assertContains(response, second_asset.name)

    def test_asset_list_filters_by_multiple_os_families(self):
        second_family = OSFamily.objects.create(name="Ubuntu", vendor="Canonical")
        second_asset = Asset.objects.create(
            name="page-ubuntu-asset",
            owner=self.owner,
            asset_type=Asset.AssetType.COMPUTER,
        )
        second_asset.groups.add(self.group)
        AssetOS.objects.create(asset=self.asset, family=self.family, version=self.version)
        AssetOS.objects.create(asset=second_asset, family=second_family)

        self.client.force_login(self.user)
        response = self.client.get(
            "/asset/",
            data={"os_family": [str(self.family.id), str(second_family.id)]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.asset.name)
        self.assertContains(response, second_asset.name)

    def test_staff_user_list_is_scoped_and_available(self):
        grouped_user = User.objects.create_user(
            username="grouped-user",
            email="grouped-user@example.local",
            password="x",
        )
        self.group.members.add(grouped_user)
        self.client.force_login(self.user)
        response = self.client.get("/user/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user.email)
        self.assertContains(response, grouped_user.email)
        self.assertNotContains(response, self.owner.email)

    def test_non_staff_user_sees_only_profile(self):
        member = User.objects.create_user(
            username="member-profile",
            email="member-profile@example.local",
            password="x",
        )
        self.client.force_login(member)
        response = self.client.get("/user/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your profile")
        self.assertContains(response, member.email)
        self.assertNotContains(response, self.user.email)
        self.assertNotContains(response, ">Admin<", html=False)

    def test_user_detail_exists_and_is_scoped(self):
        grouped_user = User.objects.create_user(
            username="grouped-detail",
            email="grouped-detail@example.local",
            password="x",
        )
        self.group.members.add(grouped_user)
        self.client.force_login(self.user)
        response = self.client.get(f"/user/{grouped_user.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, grouped_user.email)

        hidden_user = User.objects.create_user(
            username="hidden-detail",
            email="hidden-detail@example.local",
            password="x",
        )
        hidden_response = self.client.get(f"/user/{hidden_user.id}/")
        self.assertEqual(hidden_response.status_code, 404)

    def test_asset_detail_exists_on_asset_id_path(self):
        self.client.force_login(self.user)
        response = self.client.get(f"/asset/{self.asset.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.asset.name)

    def test_assets_legacy_path_redirects_to_new_list(self):
        self.client.force_login(self.user)
        response = self.client.get("/assets/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/asset/", response.headers["Location"])

    def test_edit_view_updates_asset_and_os_features(self):
        self.client.force_login(self.user)
        response = self.client.post(
            f"/asset/{self.asset.id}/edit/",
            data={
                "asset-name": "page-asset-1-updated",
                "asset-asset_type": Asset.AssetType.COMPUTER,
                "asset-owner": self.owner.id,
                "asset-status": Asset.Status.ACTIVE,
                "asset-groups": [self.group.id],
                "asset-asset_tag": "TAG-1",
                "asset-serial_number": "SER-1",
                "asset-manufacturer": "Dell",
                "asset-model": "Latitude",
                "asset-notes": "updated",
                "os-family": self.family.id,
                "os-version": self.version.id,
                "os-patch_level": "2026-02 CU",
                "os-installed_on": "2026-02-01",
                "os-support_state": AssetOS.SupportState.SUPPORTED,
                "os-auto_updates_enabled": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.name, "page-asset-1-updated")
        self.assertEqual(self.asset.asset_os.family_id, self.family.id)
        self.assertEqual(self.asset.asset_os.version_id, self.version.id)
        self.assertEqual(self.asset.asset_os.patch_level, "2026-02 CU")

    def test_can_create_port_and_interface_under_port(self):
        self.client.force_login(self.user)
        response = self.client.post(
            f"/asset/{self.asset.id}/port/add/",
            data={
                "port-name": "WIFI",
                "port-port_kind": Port.PortKind.WIFI,
                "port-notes": "wireless adapter",
            },
        )
        self.assertEqual(response.status_code, 302)
        port = Port.objects.get(asset=self.asset, name="WIFI")
        interface_response = self.client.post(
            f"/asset/{self.asset.id}/port/{port.id}/interface/add/",
            data={
                f"iface-{port.id}-identifier": "wlan0",
                f"iface-{port.id}-mac_address": "aa:bb:cc:11:22:33",
                f"iface-{port.id}-notes": "wifi interface",
            },
        )
        self.assertEqual(interface_response.status_code, 302)
        interface = NetworkInterface.objects.get(asset=self.asset, identifier="wlan0")
        self.assertEqual(interface.port_id, port.id)

    def test_can_deactivate_interface_and_port_without_delete(self):
        self.client.force_login(self.user)
        port = Port.objects.get(asset=self.asset, name="LAN")
        interface = NetworkInterface.objects.get(asset=self.asset, identifier="lan")

        interface_response = self.client.post(
            f"/asset/{self.asset.id}/port/{port.id}/interface/{interface.id}/update/",
            data={
                f"iface-row-{interface.id}-identifier": interface.identifier,
                f"iface-row-{interface.id}-mac_address": interface.mac_address or "",
                f"iface-row-{interface.id}-notes": interface.notes,
                "action": "deactivate",
            },
        )
        self.assertEqual(interface_response.status_code, 302)
        interface.refresh_from_db()
        self.assertFalse(interface.active)

        port_response = self.client.post(
            f"/asset/{self.asset.id}/port/{port.id}/update/",
            data={
                f"port-row-{port.id}-name": port.name,
                f"port-row-{port.id}-port_kind": port.port_kind,
                f"port-row-{port.id}-notes": port.notes,
                "action": "deactivate",
            },
        )
        self.assertEqual(port_response.status_code, 302)
        port.refresh_from_db()
        self.assertFalse(port.active)
