# Demo Data Fixtures

Tato složka obsahuje demo data pro ITIN systém rozdělené do logických celků.

## Struktura fixtures

1. **01_users.json** - Uživatelé systému
   - root/root (superuser)
   - itadmin (superuser)
   - jnovak (běžný uživatel)
   - pkolar (běžný uživatel)

2. **02_groups.json** - Organizační skupiny
   - Core IT
   - Helpdesk

3. **03_os_families.json** - Rodiny operačních systémů a jejich verze
   - **Windows Desktop**: 7, 8, 8.1, 10 (více verzí), 11 (více verzí)
   - **Windows Server**: 2008 R2, 2012 R2, 2016, 2019, 2022, 2025
   - **Linux Server**: Ubuntu (20.04, 22.04, 24.04), Debian (11, 12), CentOS Stream 9, Rocky Linux 9.3, AlmaLinux 9.3
   - **macOS**: Ventura (13), Sonoma (14), Sequoia (15)
   - **Linux Desktop**: Fedora Workstation (39, 40)
   - **Mobile**: Android (13, 14, 15), iOS (16, 17, 18)

4. **04_networks.json** - Síťové definice
   - Office LAN (VLAN 10)
   - Lab LAN (VLAN 20)

5. **05_assets.json** - Assety a související data
   - 3 počítače (atlas-lt-01, atlas-lt-02, lab-mini-01)
   - Přiřazené OS
   - Síťová rozhraní
   - Porty
   - IP adresy

6. **06_guest_devices.json** - Hostovská zařízení

## Načtení dat

Načtení všech fixtures najednou:
```bash
python manage.py loaddata 01_users 02_groups 03_os_families 04_networks 05_assets 06_guest_devices
```

Nebo jednotlivě:
```bash
python manage.py loaddata 01_users
python manage.py loaddata 02_groups
# atd.
```

## Přihlašovací údaje

- **root** / **root** (superuser)
- **itadmin** / **itadmin** (superuser)
- **jnovak** / **demo** (běžný uživatel)
- **pkolar** / **demo** (běžný uživatel)

## Poznámky

- Fixtures jsou číslovány prefixem (01_, 02_, ...) pro správné pořadí načítání kvůli závislostem
- Primární klíče jsou pevně definované pro zachování vazeb mezi modely
- Data jsou určena pouze pro demo a vývojové účely
