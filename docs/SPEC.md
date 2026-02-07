# IT Asset Tracker – Specification (Django 6)

## 1. Purpose
Build an internal system for managing **IT assets** with emphasis on **very fast data entry** and an **Excel-like overview** for administrators.

The system must be **extensible**: future modules may add richer IPAM, switch/patch-panel topology, port-to-port connectivity, discovery, and more.

---

## 2. Scope

### In scope (current)
- Generic **Asset** inventory (starting with computers; future asset types supported)
- Ownership (assigned person)
- Organizational groups and permissions
- Microsoft O365 (Entra ID) SSO (OIDC)
- Lightweight IPv4 IPAM (networks, interfaces, IP allocations)
- Ports model (introduced now; simplified UI)
- Temporary guest devices (time-limited)
- Exports for DHCP and 802.1X RADIUS
- Docker-based development + production-like deployment

### Planned future extensions (not implemented now)
- Full IPAM (pools, utilization, conflict tooling)
- Patch panels / wall outlets / switch topology and cabling
- Automated discovery and reconciliation

---

## 3. Technology Stack

### Backend
- Python 3.12+
- **Django 6**
- Django REST Framework (DRF)
- PostgreSQL
- ASGI server: Daphne

### Frontend
- Tailwind CSS
- HTMX **1.9.12** for server-driven interactivity (partials, modals, forms)
- **React (limited scope)**: only for the Excel-style asset overview table

### Infrastructure
- Docker + Docker Compose

---

## 4. Architecture Overview

Hybrid UI:
- Django templates provide layout, navigation, forms, detail pages
- HTMX handles partial updates without custom JS
- React is embedded only on the overview table page to deliver a power-user “spreadsheet” UX

Django remains the single source of truth for:
- permissions
- validation
- business logic
- auditability

---

## 5. Authentication & User Lifecycle

### Authentication
- Microsoft Entra ID / O365 login via OIDC
- Session-based auth (no JWT)
- On first login, create a local Django user (JIT provisioning)
- Match identities by stable Entra identifier (tenant_id + oid/sub)

### User lifecycle
- Users are not deleted automatically
- If user disappears from Entra ID: mark local user inactive and revoke roles
- Historical references (ownership/audit) remain intact

---

## 6. Permission Model

Roles:
- **Superuser**: full access
- **Group admin**: CRUD assets within their groups; manage guests for their groups
- **Group member**: read-only for assets in their groups

Permissions are enforced server-side.

---

## 7. Data Model

### 7.1 OrganizationalGroup
Fields:
- name (unique)
- description (optional)
- default_vlan_id (optional; for RADIUS export policy)

Relations:
- members (M2M User)
- admins (M2M User)

---

### 7.2 Asset (base model)
Generic asset model enabling future types (monitors, printers, etc.).

Fields:
- name / hostname (optional, not unique)
- asset_type (enum): COMPUTER | NOTEBOOK | SERVER | MONITOR | KEYBOARD | DEVICE | NETWORK | PRINTER | MOBILE | TABLET | BYOD | OTHER
- asset_tag (optional)
- serial_number (optional)
- manufacturer (optional)
- model (optional)
- owner (FK → User, optional / nullable)
- groups (M2M → OrganizationalGroup)
- status (enum): ACTIVE | STORED | RETIRED | LOST
- notes (optional)
- created_at / updated_at

No `purchase_date`, no `last_seen_at`.

---

### 7.3 OS catalog (normalized)
OS info must be selected from DB, not free text.

#### OSFamily
Examples: “Windows 10 Pro”, “Windows 11 Enterprise”, “Ubuntu”, “Debian”.
- name (unique, required)
- vendor (optional)

#### OSVersion
Examples: “22H2”, “23H2”, “24.04”, “12”.
- family (FK → OSFamily, required)
- version (string, required)
Constraint:
- unique (family, version)

#### AssetOS
Assignment of OS to an asset.
- asset (FK → Asset, unique per asset)
- family (FK → OSFamily, required)
- version (FK → OSVersion, nullable)

---

### 7.4 Lightweight IPv4 IPAM
Minimal IPv4 tracking for DHCP and RADIUS workflows.

#### Network
- name (unique, required)
- vlan_id (optional)
- cidr (IPv4 CIDR, required)
- gateway (optional)
- dhcp_enabled (bool, default true)
- notes (optional)

#### NetworkInterface
Represents an interface belonging to an asset (e.g. “eth0”, “lan”, “nic1”).
- asset (FK → Asset, required)
- identifier (string, required)
- mac_address (nullable; validated format; unique when present)
- notes (optional)
Constraint:
- unique (asset, identifier)

#### IPAddress
Represents an IPv4 allocation that may be assigned to an interface.
- network (FK → Network, required)
- address (IPv4, required)
- status (enum): STATIC | DHCP_RESERVED | DHCP_DYNAMIC | DEPRECATED
- assigned_interface (FK → NetworkInterface, nullable)
- hostname (optional; default to asset.name in exports)
- active (bool, default true)

Validation rules:
- address must be within network.cidr
- unique (network, address)
- allow multiple IPs historically, but enforce:
  - max **one ACTIVE IP per (network, assigned_interface)**

Rationale:
- prevents “two active IPs in same subnet on same NIC”
- allows history and doesn’t block future multi-IP support

---

### 7.5 Ports (introduced now; simplified UI)
Ports are introduced now to avoid refactoring later when topology is added.

#### Port
A port belongs to an asset.
- asset (FK → Asset, required)
- name (string, required)  # e.g. “LAN”, “eth0”, later “Gi1/0/24”
- port_kind (enum): RJ45 | SFP | WIFI | VIRTUAL | OTHER
- notes (optional)
Constraint:
- unique (asset, name)

Relationship:
- `NetworkInterface.port` is the single source of truth for interface-to-port assignment

Current phase: no cabling, no link model.
Future: add Link/Cable (port ↔ port).

---

### 7.6 GuestDevice
Temporary entry for network access.
- description (optional)
- sponsor (FK → User)
- groups (M2M → OrganizationalGroup)
- mac_address (required)
- valid_from
- valid_until
- enabled

---

## 8. UX: Very Simple Entry (MINIMAL CLICKS)

### 8.1 Defaults and auto-creation
When creating an Asset of type COMPUTER, auto-create:
- default NetworkInterface (`identifier = "lan"`, mac optional)
- default Port (`name = "LAN"`, `port_kind = RJ45`) linked to that interface

So the usual case requires **no additional clicks** to “add interface”.

### 8.2 Quick Add (one screen / modal)
Quick Add must allow creating an asset with optional network data in a single form:
- name, owner, groups, status
- optional: asset_tag / serial
- optional: OS family + version
- optional: network + IP + MAC (for the default interface)

### 8.3 Bulk entry
Provide batch entry via:
- React table paste, or
- a simple “Paste CSV-like text” dialog that creates/updates multiple assets

---

## 9. Asset Overview – Excel-style Table

Requirements:
- one row per Asset (initially filter type=COMPUTER)
- inline editable cells
- keyboard navigation (Enter/Escape/Tab)
- in-cell validation feedback
- no full page reloads

Editable fields (minimum):
- owner
- status
- groups
- OS family + version
- network data via two spreadsheet modes:
  - Asset view: expandable Ports -> Interfaces -> IPs hierarchy
  - Interface view: one row per interface with Port, MAC, Network, IP

---

## 10. Hybrid UI: React Spreadsheet Component

React is used **only** for the overview table.

Responsibilities:
- render spreadsheet table
- inline edit and bulk edits (Excel paste)
- filter/sort/pagination UX
- optional row virtualization

Integration:
Django injects mount point config:
- API base URL
- CSRF token
- can-edit flag

Auth & CSRF:
- Django session auth
- CSRF token included in mutating requests

---

## 11. API Design (DRF)

OpenAPI / Swagger:
- OpenAPI schema: `GET /api/schema/`
- Swagger UI: `GET /api/docs/`
- ReDoc: `GET /api/redoc/`

Authentication:
- `POST /api/auth/login/` with `username` or `email` and `password`
- API supports session auth and token auth
- Token header format: `Authorization: Token <token>`
- Tokens are provisioned in Django admin only (no API endpoint creates tokens)

Assets:
- `POST /api/assets/`
- `GET /api/assets/` (filters: q, group, owner, status, type)
- `PATCH /api/assets/{id}/`
- `POST /api/assets/{id}/port-interface/` (create port + interface and link both to asset)

Bulk update:
- `POST /api/assets/bulk_update/`
  - validates per row
  - enforces permissions per row
  - returns per-row success/error

Interfaces:
- `POST /api/interfaces/`
- `GET /api/interfaces/` (filters: q, asset, active)
- `PATCH /api/interfaces/{id}/`

Interface bulk update:
- `POST /api/interfaces/bulk_update/`
  - validates per row
  - enforces permissions per row
  - returns per-row success/error

Ports:
- `POST /api/ports/`
- `GET /api/ports/` (filters: q, asset, active)
- `PATCH /api/ports/{id}/`

Lookups:
- `GET /api/users/?q=`
- `POST /api/groups/` (superuser only)
- `GET /api/groups/?q=`
- `POST /api/os-families/` (superuser only)
- `GET /api/os-families/?q=`
- `GET /api/os-versions/?family_id=&q=`
- `GET /api/networks/?q=`

Request body examples:

- `POST /api/auth/login/`
```json
{
  "email": "admin@example.local",
  "password": "secret"
}
```

- `POST /api/assets/`
```json
{
  "name": "atlas-lt-01",
  "asset_type": "NOTEBOOK",
  "owner": null,
  "groups": [1, 2],
  "status": "ACTIVE",
  "asset_tag": "INV-1001",
  "serial_number": "SN-001",
  "manufacturer": "Dell",
  "model": "Latitude 7450",
  "notes": "User-facing notebook",
  "metadata": {"location": "HQ-201"},
  "os_family": 3,
  "os_version": 12
}
```

- `PATCH /api/assets/{id}/`
```json
{
  "status": "STORED",
  "owner": null,
  "groups": [2],
  "os_family": 3,
  "os_version": 12
}
```

- `POST /api/assets/{id}/port-interface/`
```json
{
  "port_name": "LAN-2",
  "port_kind": "RJ45",
  "port_notes": "Docking station",
  "interface_identifier": "eth1",
  "interface_mac_address": "aa:bb:cc:11:22:33",
  "interface_notes": "Secondary NIC"
}
```

- `POST /api/ports/`
```json
{
  "asset": 10,
  "name": "WIFI",
  "port_kind": "WIFI",
  "notes": "Wireless adapter",
  "active": true
}
```

- `POST /api/interfaces/`
```json
{
  "asset": 10,
  "port": 55,
  "identifier": "wlan0",
  "mac_address": "aa:bb:cc:44:55:66",
  "active": true,
  "notes": "Primary wireless",
  "network": 4,
  "address": "10.20.30.40",
  "ip_status": "STATIC",
  "hostname": "atlas-lt-01"
}
```

- `PATCH /api/interfaces/{id}/`
```json
{
  "mac_address": "aa:bb:cc:44:55:99",
  "network": 4,
  "address": "10.20.30.41",
  "ip_status": "STATIC",
  "hostname": "atlas-lt-01"
}
```

- `POST /api/assets/bulk_update/`
```json
{
  "rows": [
    {"id": 10, "status": "ACTIVE", "owner": null, "groups": [1]},
    {"id": 11, "status": "STORED", "os_family": 3, "os_version": 12}
  ]
}
```

- `POST /api/interfaces/bulk_update/`
```json
{
  "rows": [
    {"id": 101, "mac_address": "aa:bb:cc:dd:ee:01"},
    {"id": 102, "network": 4, "address": "10.20.30.50", "ip_status": "STATIC", "hostname": "node-102"}
  ]
}
```

- `POST /api/groups/` (superuser only)
```json
{
  "name": "Operations",
  "description": "Ops group",
  "default_vlan_id": 120
}
```

- `POST /api/os-families/` (superuser only)
```json
{
  "name": "Ubuntu",
  "vendor": "Canonical",
  "platform_type": "SERVER",
  "supports_domain_join": false
}
```

---

## 12. Exports (written to /exports)

DHCP export:
- `python manage.py export_dhcp --out=/exports/dhcp.json`
- include assets/interfaces with MAC
- include static/reserved IPs if present
- include valid enabled GuestDevice entries

RADIUS export:
- `python manage.py export_radius --out=/exports/radius-authorize`
- include MAC identities from interfaces and guests
- optional VLAN mapping from group.default_vlan_id

---

## 13. Docker Setup

Development:
- Django with auto-reload
- PostgreSQL
- mounted source
- exports volume

Production-like:
- Daphne ASGI
- PostgreSQL
- collected static files
- exports volume

---

## 14. Quality & Testing
Tests for:
- permissions
- OS catalog constraints
- IP-in-network validation
- “one active IP per interface per network” constraint
- exporter output sanity
- bulk update error reporting

---

## 15. Future Extensions
The current models (Asset, NetworkInterface, IPAddress, Port) must support additive extensions:
- topology (Link/Cable, switch ports, patch panels)
- richer IPAM (pools, utilization, conflict UI)
- discovery agents and reconciliation workflows
