# ITIN - IT Asset Tracker

Web application for tracking IT inventory: assets, network interfaces, IP addresses, OS records, locations, guest device registrations, and network approval workflows.

Built with Django 6, PostgreSQL, Redis, Celery, and django-allauth.

## Quick start

```bash
cp .env.example .env        # edit values as needed
docker compose build
docker compose up -d
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser
```

The application runs at **http://localhost:8000/**.

## Project structure

```
itin/             Django project settings, URLs, WSGI/ASGI
inventory/        Main app: models, views, templates, API
templates/        Shared and app-level templates
static/           Static assets
```

## Environment variables

All configuration is done via environment variables. See `.env.example` for a full list.

### Core

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | `dev-secret-key` | Secret key (change in production) |
| `DJANGO_DEBUG` | `1` | Debug mode (`0` for production) |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated allowed hosts |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | | Comma-separated trusted origins for CSRF |
| `DJANGO_SITE_ID` | `1` | Django sites framework ID |

### Database (PostgreSQL)

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_DB` | `itin` | Database name |
| `POSTGRES_USER` | `itin` | Database user |
| `POSTGRES_PASSWORD` | `itin` | Database password |
| `POSTGRES_HOST` | `db` | Database host |
| `POSTGRES_PORT` | `5432` | Database port |

### Redis

| Variable | Default | Description |
|---|---|---|
| `REDIS_HOST` | `redis` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_DB` | `0` | Redis database number |
| `REDIS_PASSWORD` | | Redis password (optional) |

## Authentication: Microsoft Entra ID (O365 SSO)

The application uses [django-allauth](https://docs.allauth.org/) OpenID Connect. In this project, the provider is configured in `itin/settings.py` through the `SOCIALACCOUNT_PROVIDERS` dictionary, so it is **settings-based configuration**. You do not need to create provider credentials in Django admin.

### 1. Set environment variables

Required:

```env
ENTRA_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
ENTRA_OIDC_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
ENTRA_OIDC_CLIENT_SECRET=your-client-secret-value
```

Optional:

```env
ENTRA_OIDC_PROVIDER_ID=entra
```

`ENTRA_OIDC_PROVIDER_ID` defaults to `entra`, and allauth builds the callback URL as:

`/accounts/oidc/<provider_id>/login/callback/`

With the default value, the callback path is:

`/accounts/oidc/entra/login/callback/`

### 2. Configure redirect URI in Azure App Registration

In Azure Portal > Microsoft Entra ID > App registrations > your app > Authentication, set Web redirect URI to:

`https://itin.ujf.cas.cz/accounts/oidc/entra/login/callback/`

If you change `ENTRA_OIDC_PROVIDER_ID`, update the redirect URI accordingly.

### 3. Configure Django Site domain

In Django admin (`/admin/sites/site/`), set the Site domain to your real host (for example `itin.ujf.cas.cz`). allauth uses this value when generating absolute URLs.

### 4. Restart web container

```bash
docker compose up -d web
```

The Entra ID login option appears on `/accounts/login/`. Users are created on first successful SSO login and matched by email.

### Allauth behavior

| Setting | Value | Effect |
|---|---|---|
| `SOCIALACCOUNT_LOGIN_ON_GET` | `True` | Clicking the provider link immediately redirects to Microsoft (no confirmation page) |
| `SOCIALACCOUNT_AUTO_SIGNUP` | `True` | New users are created automatically on first login |
| `SOCIALACCOUNT_EMAIL_AUTHENTICATION` | `True` | Existing users are matched by email address |
| `SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT` | `True` | Social account is auto-linked to existing user with same email |

## Running services

```bash
docker compose up -d              # all services (web, db, redis, celery, qcluster)
docker compose up -d web          # web server only
docker compose logs -f web        # follow web logs
docker compose run --rm web python manage.py migrate    # run migrations
docker compose run --rm web python manage.py shell      # Django shell
```

## Production notes

- Set `DJANGO_DEBUG=0`
- Set a strong `DJANGO_SECRET_KEY`
- Set `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` to your domain
- Set `DJANGO_SESSION_COOKIE_SECURE=1` and `DJANGO_CSRF_COOKIE_SECURE=1`
- Use `docker-compose.prod.yml` if available
