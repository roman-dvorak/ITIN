# Agent Rules for IT Asset Tracker

These rules guide AI-assisted development (GitHub Copilot / ChatGPT agents) for this repository.

---

## 1. General Principles

* Prefer clarity over cleverness
* Keep code readable and explicit
* Follow Django conventions unless there is a strong reason not to
* Avoid premature optimization

---

## 2. Architecture Rules

* Django is the authoritative backend
* Business logic must live on the server
* React is **allowed only** for the computer overview table
* Do not introduce SPA routing
* HTMX is preferred for all non-table interactivity

---

## 3. Frontend Rules

* Use Tailwind CSS utility classes only
* No custom JavaScript unless strictly required
* React components must:

  * be isolated
  * communicate only via documented API endpoints
  * not contain authentication logic

---

## 4. API Rules

* All API endpoints must enforce permissions server-side
* Use PATCH for partial updates
* Bulk operations must validate each row independently
* Never trust client-side validation alone

---

## 5. Data & Models

* Do not delete records silently
* Prefer deactivation over deletion
* All models should be extensible for future network features
* Avoid hard-coding business rules into templates

---

## 6. Security

* Always enforce CSRF protection
* Use Django session authentication
* Never expose secrets in frontend code

---

## 7. Testing Expectations

* Add tests when introducing:

  * new permissions
  * new export logic
  * new bulk update behavior
* During regular development, run only targeted tests for changed areas
* Run the full test suite only when explicitly requested by the user

---

## 8. What NOT to do

* Do not convert the project into a full SPA
* Do not bypass Django permissions in React
* Do not introduce unnecessary microservices

---

## 9. Future-proofing

* New modules (IPAM, topology) must be additive
* Existing APIs must remain backward-compatible
* Prefer migrations over destructive changes
