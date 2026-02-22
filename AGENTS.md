# Agent Rules for IT Asset Tracker

These rules guide AI-assisted development (GitHub Copilot / ChatGPT / Warp agents) for this repository.

---

## 1. General Principles

* Prefer clarity over cleverness
* Keep code readable and explicit
* Follow Django conventions unless there is a strong reason not to
* Avoid premature optimization
* Respect the existing codebase structure and patterns

---

## 2. Architecture Rules

### Backend
* Django 6 is the authoritative backend
* Business logic must live on the server
* Use Django ORM for all database operations
* Background tasks use Celery with Redis broker
* Authentication: Django session + django-allauth (Microsoft Entra ID / O365 SSO)

### Frontend
* Server-rendered templates with Django template language
* React is **allowed only** for the asset overview table (`asset_overview.html`)
* Do not introduce SPA routing
* HTMX is preferred for all non-table interactivity (pagination, filters, modals)
* Tailwind CSS for all styling

---

## 3. Data Model Overview

Core entities:
* **Asset** - IT devices with types (Computer, Server, Monitor, Network, Mobile, BYOD, etc.)
* **Location** - hierarchical location tree with path caching
* **OrganizationalGroup** - groups with members and admins for permission management
* **NetworkInterface** & **Port** - network connectivity (MAC, IP assignments)
* **IPAddress** & **Network** - IP address management with VLAN support
* **AssetOS** & **OSFamily** - multiple OS records per asset with support status tracking
* **GuestDevice** - self-service guest device registration with approval workflow
* **NetworkApprovalRequest** - network access approval workflow
* **UserProfile** - extended user metadata (synced from O365)

Important patterns:
* Use `Asset.objects.visible_to(user)` and `Asset.objects.editable_by(user)` for permission filtering
* Assets support multiple OS entries via `os_entries` relation
* Locations use `path_cache` for efficient hierarchy queries
* MAC addresses are normalized to lowercase with colons
* Use `simple_history` for audit trail on Asset model

---

## 4. Frontend Rules

* Use Tailwind CSS utility classes only
* No custom JavaScript unless strictly required
* React components must:
  * be isolated to their designated area
  * communicate only via documented API endpoints
  * not contain authentication logic
  * not bypass Django permissions

* HTMX patterns:
  * Use for dynamic updates, filtering, pagination
  * Return partials from views (e.g., `partials/asset_table.html`)
  * Keep HTMX attributes in templates, not in JavaScript

---

## 5. API Rules

* Django REST Framework for all API endpoints
* All API endpoints must enforce permissions server-side
* Use `AssetObjectPermission` for asset-related endpoints
* Use PATCH for partial updates
* Bulk operations must validate each row independently
* Never trust client-side validation alone
* API authentication: session auth + optional token auth
* Use `drf-spectacular` for API schema generation

Existing API endpoints:
* `/api/assets/` - asset CRUD with filtering
* `/api/locations/` - location hierarchy
* `/api/guests/` - guest device management
* `/api/interfaces/` - network interface management
* `/api/bulk-*` - bulk update operations

---

## 6. Data & Models

* Do not delete records silently
* Prefer deactivation over deletion (use `active` field where available)
* Use `Asset.Status.RETIRED` / `DISCARDED` instead of deletion
* All models should be extensible for future network features
* Avoid hard-coding business rules into templates
* Use model `clean()` methods for validation
* MAC addresses must be validated with `validate_mac()` and normalized with `normalize_mac()`

---

## 7. Permissions & Access Control

* Assets are scoped by `OrganizationalGroup`
* Members can view assets in their groups
* Admins can edit assets in their groups
* Superusers have unrestricted access
* Use `visible_assets_for_user(user)` helper in views
* Use `can_edit_asset(user, asset)` helper before modifications
* Guest device sponsors can manage their own registrations
* Staff users can approve/reject guest devices and network requests

---

## 8. Background Tasks

* Use Celery for asynchronous tasks
* Management commands for scheduled tasks:
  * `export_dhcp` - generate DHCP configuration
  * `export_radius` - generate RADIUS configuration
  * `sync_o365` - sync user metadata from Office 365
  * `import_assets_csv` - bulk import from CSV

---

## 9. Security

* Always enforce CSRF protection
* Use Django session authentication
* Never expose secrets in frontend code
* Microsoft Entra ID configured via environment variables
* Token authentication available for API clients (provisioned in admin)

---

## 10. Testing Expectations

* Add tests when introducing:
  * new permissions
  * new export logic
  * new bulk update behavior
  * new API endpoints
* Do not run tests during regular development unless the user explicitly asks for it
* Run targeted tests only when explicitly requested by the user
* Run the full test suite only when explicitly requested by the user

---

## 11. What NOT to do

* Do not convert the project into a full SPA
* Do not bypass Django permissions in React or API
* Do not introduce unnecessary microservices
* Do not hardcode environment-specific values
* Do not commit `.env` file
* Do not break existing API contracts

---

## 12. Development Workflow

* Use Docker Compose for local development
* Environment variables in `.env` (based on `.env.example`)
* Migrations: always generate and review before applying
* Run `python manage.py check` before committing
* Use `docker compose run --rm web python manage.py <command>`

---

## 13. Future-proofing

* New modules (IPAM, topology, asset lifecycle) must be additive
* Existing APIs must remain backward-compatible
* Prefer migrations over destructive changes
* Design for multi-site/multi-organization scaling
