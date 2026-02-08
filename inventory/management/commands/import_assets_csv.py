"""
Import assets from CSV file.

Usage:
    python manage.py import_assets_csv ~/Stažené/sit_uprava_clean_type_unified.csv
"""
import csv
import re
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from inventory.models import (
    Asset,
    AssetOS,
    NetworkInterface,
    OrganizationalGroup,
    OSFamily,
    Port,
)

User = get_user_model()


# Mapping CSV Type -> Asset.AssetType
TYPE_MAP = {
    'Notebook': Asset.AssetType.NOTEBOOK,
    'Computer': Asset.AssetType.COMPUTER,
    'Server': Asset.AssetType.SERVER,
    'Monitor': Asset.AssetType.MONITOR,
    'Keyboard': Asset.AssetType.KEYBOARD,
    'Device': Asset.AssetType.DEVICE,
    'Other': Asset.AssetType.OTHER,
    'Network': Asset.AssetType.NETWORK,
    'Mobile': Asset.AssetType.MOBILE,
    'Tablet': Asset.AssetType.TABLET,
    'BYOD': Asset.AssetType.BYOD,
}

# Mapping OS strings to OS family names
OS_FAMILY_PATTERNS = [
    # Windows patterns
    (r'Windows\s*11|Win\s*11|win\s*11', 'Windows 11'),
    (r'Windows\s*10|Win\s*10|win\s*10', 'Windows 10'),
    (r'Windows\s*8\.1|Win\s*8\.1', 'Windows 8.1'),
    (r'Windows\s*8|Win\s*8', 'Windows 8'),
    (r'Windows\s*7|Win\s*7|WIN\s*7', 'Windows 7'),
    (r'Windows\s*XP|Win\s*XP|WIN\s*XP|WIN98', 'Windows XP'),
    (r'Windows\s*Vista|Vista', 'Windows Vista'),
    (r'Windows\s*Server\s*2022', 'Windows Server 2022'),
    (r'Windows\s*Server\s*2019', 'Windows Server 2019'),
    (r'Windows\s*Server\s*2016', 'Windows Server 2016'),
    (r'Windows\s*Server\s*2012', 'Windows Server 2012 R2'),
    (r'Windows\s*Server\s*2008', 'Windows Server 2008 R2'),
    (r'Windows\s*Server\s*2003|Netware', 'Windows Server 2003'),
    (r'Windows\s*Embedded|Win\s*Embedded', 'Windows Embedded'),
    (r'Windows\s*IoT', 'Windows 10 IoT'),
    # Linux patterns
    (r'Ubuntu', 'Ubuntu'),
    (r'Debian', 'Debian'),
    (r'Rocky\s*Linux', 'Rocky Linux'),
    (r'AlmaLinux', 'AlmaLinux'),
    (r'CentOS|centos', 'CentOS'),
    (r'Fedora', 'Fedora Workstation'),
    (r'Scientific\s*[Ll]inux|SL\s*\d', 'Scientific Linux'),
    (r'Linux\s*Mint', 'Linux Mint'),
    (r'Raspbian', 'Raspbian'),
    (r'OpenWRT', 'OpenWRT'),
    # macOS
    (r'macOS|MAC\s*OS|Mac\s*OS', 'macOS'),
    (r'iOS|iPadOS', 'iOS'),
    # Mobile
    (r'Android', 'Android'),
    # Other
    (r'RouterOS', 'RouterOS'),
    (r'Synology|DSM', 'Synology DSM'),
    (r'QTS', 'QNAP QTS'),
    (r'OPNSense|pfSense', 'OPNsense'),
    (r'Cisco\s*IOS', 'Cisco IOS'),
    (r'GNU/Linux|Linux', 'Linux'),
]

# OS family metadata
OS_FAMILY_METADATA = {
    'Windows XP': {'family': OSFamily.FamilyType.WINDOWS},
    'Windows Vista': {'family': OSFamily.FamilyType.WINDOWS},
    'Windows Embedded': {'family': OSFamily.FamilyType.WINDOWS},
    'Windows 10 IoT': {'family': OSFamily.FamilyType.WINDOWS},
    'Windows Server 2003': {'family': OSFamily.FamilyType.WINDOWS},
    'CentOS': {'family': OSFamily.FamilyType.LINUX},
    'Scientific Linux': {'family': OSFamily.FamilyType.LINUX},
    'Linux Mint': {'family': OSFamily.FamilyType.LINUX},
    'Raspbian': {'family': OSFamily.FamilyType.LINUX},
    'OpenWRT': {'family': OSFamily.FamilyType.NETWORK_OS},
    'RouterOS': {'family': OSFamily.FamilyType.NETWORK_OS},
    'Synology DSM': {'family': OSFamily.FamilyType.NAS_OS},
    'QNAP QTS': {'family': OSFamily.FamilyType.NAS_OS},
    'OPNsense': {'family': OSFamily.FamilyType.NETWORK_OS},
    'Cisco IOS': {'family': OSFamily.FamilyType.NETWORK_OS},
    'Android': {'family': OSFamily.FamilyType.ANDROID},
    'Linux': {'family': OSFamily.FamilyType.LINUX},
}


def normalize_mac(value):
    """Normalize MAC address to lowercase colon-separated format."""
    if not value:
        return None
    value = value.strip().lower().replace('-', ':')
    # Validate format
    if re.match(r'^([0-9a-f]{2}[:]){5}([0-9a-f]{2})$', value):
        return value
    return None


def detect_os_family(os_string):
    """Detect OS family from OS string."""
    if not os_string:
        return None
    os_string = os_string.strip()
    if not os_string or os_string in ('?', '??', 'neznámý', '', ' '):
        return None
    
    for pattern, family_name in OS_FAMILY_PATTERNS:
        if re.search(pattern, os_string, re.IGNORECASE):
            return family_name
    return None


class Command(BaseCommand):
    help = 'Import assets from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to CSV file')
        parser.add_argument('--dry-run', action='store_true', help='Do not save, just show what would be done')
        parser.add_argument('--owner-email', type=str, default=None, help='Email of default owner')

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        dry_run = options['dry_run']
        owner_email = options.get('owner_email')

        # Get or create default owner
        if owner_email:
            owner = User.objects.filter(email=owner_email).first()
            if not owner:
                self.stderr.write(f'User with email {owner_email} not found')
                return
        else:
            owner = User.objects.filter(is_superuser=True).first()
            if not owner:
                owner = User.objects.first()
            if not owner:
                self.stderr.write('No users found in database')
                return

        self.stdout.write(f'Using owner: {owner.email}')

        # Read CSV
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            rows = list(reader)

        self.stdout.write(f'Read {len(rows)} rows from CSV')

        # Collect unique values
        ou_values = set()
        os_values = set()
        for row in rows:
            ou = row.get('ou', '').strip()
            if ou and not ou.startswith('(') and 'Win ' not in ou:
                ou_values.add(ou)
            os_val = row.get('Operační systém', '').strip()
            detected = detect_os_family(os_val)
            if detected:
                os_values.add(detected)

        self.stdout.write(f'Found {len(ou_values)} unique OUs: {sorted(ou_values)}')
        self.stdout.write(f'Found {len(os_values)} unique OS families: {sorted(os_values)}')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - not saving anything'))

        # Create groups
        groups_map = {}
        existing_groups = {g.name: g for g in OrganizationalGroup.objects.all()}
        for ou in sorted(ou_values):
            if ou in existing_groups:
                groups_map[ou] = existing_groups[ou]
                self.stdout.write(f'  Group exists: {ou}')
            else:
                if not dry_run:
                    group = OrganizationalGroup.objects.create(name=ou)
                    groups_map[ou] = group
                self.stdout.write(self.style.SUCCESS(f'  Created group: {ou}'))

        # Create OS families
        os_family_map = {}
        existing_families = {f.name: f for f in OSFamily.objects.all()}
        for os_name in sorted(os_values):
            if os_name in existing_families:
                os_family_map[os_name] = existing_families[os_name]
                self.stdout.write(f'  OS Family exists: {os_name}')
            else:
                metadata = OS_FAMILY_METADATA.get(os_name, {
                    'family': OSFamily.FamilyType.OTHER,
                })
                if not dry_run:
                    family = OSFamily.objects.create(
                        family=metadata['family'],
                        name=os_name,
                    )
                    os_family_map[os_name] = family
                self.stdout.write(self.style.SUCCESS(f'  Created OS Family: {os_name}'))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN complete'))
            return

        # Refresh maps after creation
        groups_map = {g.name: g for g in OrganizationalGroup.objects.all()}
        os_family_map = {f.name: f for f in OSFamily.objects.all()}

        # Import assets
        created_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []

        for i, row in enumerate(rows):
            try:
                with transaction.atomic():
                    result = self._import_row(row, groups_map, os_family_map, owner)
                    if result == 'created':
                        created_count += 1
                    elif result == 'updated':
                        updated_count += 1
                    else:
                        skipped_count += 1
            except Exception as e:
                errors.append(f'Row {i+2}: {e}')
                self.stderr.write(f'Error row {i+2}: {e}')

        self.stdout.write(self.style.SUCCESS(
            f'\nImport complete: {created_count} created, {updated_count} updated, '
            f'{skipped_count} skipped, {len(errors)} errors'
        ))

    def _import_row(self, row, groups_map, os_family_map, default_owner):
        """Import a single row."""
        ou = row.get('ou', '').strip()
        host = row.get('host', '').strip()
        asset_type_str = row.get('Type', '').strip()
        device_name = row.get('Název zařízení', '').strip()
        device_type = row.get('Typ zařízení', '').strip()
        os_string = row.get('Operační systém', '').strip()
        location = row.get('Umístění (budova-místnost)', '').strip()
        inv_number = row.get('Inventární číslo', '').strip()
        mac1 = row.get('MAC_1', '').strip()
        mac2 = row.get('MAC_2', '').strip()
        notes_merged = row.get('Poznámka_sloučená', '').strip()

        # Skip rows without host name
        if not host:
            return 'skipped'

        # Skip invalid OUs
        if not ou or ou.startswith('(') or 'Win ' in ou:
            return 'skipped'

        # Map asset type
        asset_type = TYPE_MAP.get(asset_type_str, Asset.AssetType.OTHER)

        # Build unique name
        name = host

        # Build notes
        notes_parts = []
        if device_name:
            notes_parts.append(f'Zařízení: {device_name}')
        if device_type:
            notes_parts.append(f'Typ: {device_type}')
        if location:
            notes_parts.append(f'Umístění: {location}')
        if notes_merged:
            notes_parts.append(notes_merged)
        notes = '\n'.join(notes_parts)

        # Get or create asset
        asset, created = Asset.objects.get_or_create(
            name=name,
            defaults={
                'asset_type': asset_type,
                'asset_tag': inv_number or '',
                'manufacturer': '',
                'model': device_name or '',
                'owner': default_owner,
                'status': Asset.Status.ACTIVE,
                'notes': notes,
                'metadata': {'location': location} if location else {},
            }
        )

        if not created:
            # Update existing asset
            asset.notes = notes
            asset.asset_tag = inv_number or asset.asset_tag
            if location:
                asset.metadata['location'] = location
            asset.save()

        # Assign group
        if ou in groups_map:
            asset.groups.add(groups_map[ou])

        # Set OS
        os_family_name = detect_os_family(os_string)
        if os_family_name and os_family_name in os_family_map:
            os_family = os_family_map[os_family_name]
            existing_os = AssetOS.objects.filter(asset=asset, family=os_family).order_by("-id").first()
            if existing_os:
                if existing_os.version:
                    existing_os.version = ""
                    existing_os.save(update_fields=["version"])
            else:
                AssetOS.objects.create(asset=asset, family=os_family, version="")

        # Add MAC addresses as interfaces
        mac1_norm = normalize_mac(mac1)
        mac2_norm = normalize_mac(mac2)

        if mac1_norm:
            self._ensure_interface(asset, mac1_norm, 'lan')
        if mac2_norm:
            self._ensure_interface(asset, mac2_norm, 'lan2')

        return 'created' if created else 'updated'

    def _ensure_interface(self, asset, mac_address, identifier):
        """Ensure network interface exists for asset."""
        # Check if MAC already exists
        existing = NetworkInterface.objects.filter(mac_address=mac_address).first()
        if existing:
            if existing.asset_id != asset.id:
                # MAC belongs to different asset, skip
                return
            return

        # Get or create port
        port, _ = Port.objects.get_or_create(
            asset=asset,
            name='LAN' if identifier == 'lan' else 'LAN2',
            defaults={'port_kind': Port.PortKind.RJ45}
        )

        # Create interface
        interface, _ = NetworkInterface.objects.get_or_create(
            asset=asset,
            identifier=identifier,
            defaults={
                'mac_address': mac_address,
                'port': port,
                'active': True,
            }
        )
        if not interface.mac_address:
            interface.mac_address = mac_address
            interface.save()
