import json
from pathlib import Path

from django.utils import timezone

from .models import GuestDevice, IPAddress, NetworkInterface


def mac_to_radius_identity(mac_address: str) -> str:
    return mac_address.replace(":", "-").upper()


def _resolve_vlan_for_interface(interface: NetworkInterface):
    group = interface.asset.groups.filter(default_vlan_id__isnull=False).order_by("id").first()
    return group.default_vlan_id if group else None


def _resolve_vlan_for_guest(guest: GuestDevice):
    group = guest.groups.filter(default_vlan_id__isnull=False).order_by("id").first()
    return group.default_vlan_id if group else None


def build_dhcp_payload():
    interfaces = NetworkInterface.objects.filter(active=True).select_related("asset").prefetch_related(
        "ip_addresses__network",
        "asset__groups",
    )
    entries = []
    for interface in interfaces:
        if not interface.mac_address:
            continue
        ip_entries = interface.ip_addresses.filter(
            active=True,
            status__in=[IPAddress.Status.STATIC, IPAddress.Status.DHCP_RESERVED],
        ).select_related("network")
        entries.append(
            {
                "asset_id": interface.asset_id,
                "asset_name": interface.asset.name,
                "interface_id": interface.id,
                "identifier": interface.identifier,
                "mac_address": interface.mac_address,
                "ips": [
                    {
                        "address": ip.address,
                        "network": ip.network.name,
                        "cidr": ip.network.cidr,
                        "hostname": ip.hostname or interface.asset.name,
                        "status": ip.status,
                    }
                    for ip in ip_entries
                ],
            }
        )

    now = timezone.now()
    guests = GuestDevice.objects.filter(
        enabled=True,
        valid_from__lte=now,
        valid_until__gte=now,
    )
    guest_entries = [
        {
            "guest_id": guest.id,
            "mac_address": guest.mac_address,
            "description": guest.description,
            "valid_from": guest.valid_from.isoformat(),
            "valid_until": guest.valid_until.isoformat(),
        }
        for guest in guests
    ]
    return {"interfaces": entries, "guests": guest_entries}


def export_dhcp(path: str):
    payload = build_dhcp_payload()
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def build_radius_lines():
    lines = []
    interfaces = NetworkInterface.objects.filter(active=True).select_related("asset").prefetch_related("asset__groups")
    for interface in interfaces:
        if not interface.mac_address:
            continue
        identity = mac_to_radius_identity(interface.mac_address)
        line = f'{identity} Cleartext-Password := "{identity}"'
        vlan = _resolve_vlan_for_interface(interface)
        if vlan:
            line += f', Tunnel-Type := VLAN, Tunnel-Medium-Type := IEEE-802, Tunnel-Private-Group-Id := "{vlan}"'
        lines.append(line)

    now = timezone.now()
    guests = GuestDevice.objects.prefetch_related("groups").filter(
        enabled=True,
        valid_from__lte=now,
        valid_until__gte=now,
    )
    for guest in guests:
        identity = mac_to_radius_identity(guest.mac_address)
        line = f'{identity} Cleartext-Password := "{identity}"'
        vlan = _resolve_vlan_for_guest(guest)
        if vlan:
            line += f', Tunnel-Type := VLAN, Tunnel-Medium-Type := IEEE-802, Tunnel-Private-Group-Id := "{vlan}"'
        lines.append(line)
    return lines


def export_radius(path: str):
    lines = build_radius_lines()
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return output_path
