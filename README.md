# Cloud9Space RBAC

A single Django application containing reusable role-based authorization and a sample
projects business app. Implements all three phases of **Cloud9Space_RBAC_Intern_Assignment
(Revised).pdf**. Python 3.13, Django 5.2 LTS, DRF, PostgreSQL 17, JWT/session authentication,
Docker, and GitHub Actions. No application role names are used in authorization decisions.

**Start here:** [verification evidence](docs/VERIFICATION.md), [assignment checklist](docs/REQUIREMENTS.md),
[API guide](docs/API.md), [deployment runbook](docs/DEPLOYMENT.md),
[OpenAPI](docs/openapi.yml), [Postman collection](docs/cloud9.postman_collection.json).

## Architecture

```text
Django User ── UserRole ── Role (active) ── RolePermission ── Django Permission
     ├────── native User.groups ── Django Group.permissions ────────┤
     └────── native User.user_permissions ─────────────────────────┘
                                      │
                      RBACBackend → user.has_perm(code)
                                      │
                reusable StrictModelPermissions → projects API
```

`apps/rbac` owns models, policy services, serializers, API views, audit signals, Admin,
and tests. `apps/users` owns authentication endpoints and tests. `apps/projects` demonstrates
business authorization. `config/settings/{dev,test,prod}.py` separate environments.
All project-owned apps live under `apps/`; Django's built-in User, Group, Permission and
native mapping tables are reused unchanged. There is no custom user model or RBAC microservice.

The only configured authentication backend extends Django ModelBackend. Its effective
permission query unions active-role, group, and direct grants using a single DISTINCT SQL
query. Inactive users receive none; inactive roles contribute none; Django superuser behavior
is retained. No permission cache is kept, including on a reused User instance. Object-level
permissions are deliberately unsupported: project grants apply to all projects. Add explicit
tenant/object filtering before using this in a multi-tenant application.

## Fresh setup with Docker (recommended)

Requires Docker Engine/Desktop with Compose v2. Run from this repository's root:

```sh
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(64))"
# Set DJANGO_SECRET_KEY and POSTGRES_PASSWORD in .env using locally generated values.
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_demo
docker compose exec web python manage.py changepassword demo_editor
docker compose exec web python manage.py changepassword demo_reader
```

PowerShell: use `Copy-Item .env.example .env` for the first command. Compose waits for PostgreSQL
and applies migrations before starting Gunicorn. Visit `http://localhost:8000/admin/`.
`GET /health/` returns 200 and `/ready/` verifies PostgreSQL connectivity. Local ports bind
only to loopback. Database data persists in the `postgres_data` volume. `docker compose down`
retains data; `docker compose down -v` destroys it and is only appropriate for disposable data.
This Compose file is explicitly development configuration; see the separate production runbook.

Demo accounts have **unusable passwords**, never shared default credentials. The editor role
can view/add/change projects; readers receive view access through a native group. Seed execution
is idempotent and refused when DEBUG is false. No superuser is seeded. Bootstrap one with the
interactive command, then use that account to administer a different account.

## Fresh native setup

Install Python 3.13 and PostgreSQL 17. Create a database and login owned by the application;
the development/test database role needs CREATEDB to let Django create its isolated test DB.
Production application credentials should not have CREATEDB or database-superuser privileges.

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# PowerShell: .venv/Scripts/Activate.ps1
pip install -r requirements-dev.txt
cp .env.example .env
# Fill local secrets and POSTGRES_HOST/PORT/DB/USER/PASSWORD.
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo
python manage.py runserver
```

An alternative is `docker compose up -d db` to supply PostgreSQL for native development.
Use `POSTGRES_HOST=localhost` outside Compose. Commit migrations; never modify DB tables manually.
`python manage.py makemigrations --check --dry-run` detects uncommitted schema changes.

## Configuration

| Variable | Purpose |
| --- | --- |
| DJANGO_SETTINGS_MODULE | `config.settings.dev`, `.test`, or `.prod` |
| DJANGO_SECRET_KEY | Random 50+ character production secret; no production fallback |
| DJANGO_ALLOWED_HOSTS | Comma-separated hostnames, without schemes; no wildcard in production |
| POSTGRES_DB / USER / PASSWORD / HOST / PORT | PostgreSQL connection settings |
| CSRF_TRUSTED_ORIGINS | Production HTTPS origins, comma separated |
| TRUST_PROXY_PROTO | `1` only when a trusted TLS proxy overwrites forwarded protocol headers |
| TEST_SQLITE | `1` for limited local unit tests only; never a deployment database |

`.env` is loaded without overriding already-set process variables. Production fails fast on
missing secrets/hosts, disables DEBUG, enforces HTTPS, secure cookies, HSTS and frame protection.
Serve behind a trusted reverse proxy that terminates TLS. PostgreSQL connections use a five-second
connect timeout and health checking. Production session/JWT signing secrets belong in a secret
manager or host-protected environment file, never in image layers or GitHub source.

## Authorization and administrative policy

* Every protected API requires authentication. GET/HEAD/OPTIONS require `view_*`; POST requires
  `add_*`; PUT/PATCH requires `change_*`; DELETE requires `delete_*`. Publishing separately
  requires `projects.publish_project` and cannot be achieved via the ordinary serializer.
* RBAC API administration requires `rbac.manage_rbac`. A superuser grants it to a **different**
  account using native User permissions in Admin. Delegated administrators can only distribute
  business permissions they already hold. Auth/admin/contenttypes/sessions/RBAC permissions
  can only be delegated by superusers. Delegated admins cannot alter staff/superuser assignments.
* No account, including a superuser, can assign/revoke its own roles or edit a role it holds.
  Native User/Group/Role/assignment Admin mutations require a superuser, even when staff have
  forged requests or native model permissions. Superusers cannot edit their own User record or
  groups they belong to. Use a second administrator for these changes.
* System roles are immutable through APIs/Admin, including mappings and deletion. They are
  created and maintained only by reviewed data migrations. Assignment/revocation requires a
  superuser. Normal roles can be deactivated with PATCH; existing assignments remain visible
  but contribute no grants. Delete removes their role mappings and assignments with audit events.
* Only superusers can mutate the custom permission catalog. Runtime permissions must use
  `projects.custom_<name>` and the Project content type. Only their display name is editable.
  Generated and model-declared identifiers are protected. In-use custom permissions cannot be
  deleted until all three grant sources are revoked. A new permission does **nothing** until an
  application operation explicitly checks it. Never use the `custom_` namespace for hard-coded
  application checks; declare stable code-required permissions in model Meta instead.
* Group/membership/direct permission management uses native Django Admin rather than duplicate
  APIs or tables, as permitted by the PDF. Password changes use Django's native validation.

Administrative API writes and native Admin writes share a PostgreSQL row lock on the stable
`rbac.manage_rbac` Permission row and execute transactionally. Permission checks are repeated
after acquiring it. This serializes low-volume administration across workers and prevents
check/write races between supported control surfaces. Ordinary project requests do not lock it.
SQLite tests cannot prove PostgreSQL locking semantics; CI uses PostgreSQL.

The database/ORM shell and data migrations are trusted maintenance interfaces, not an untrusted
authorization boundary. Do not use `QuerySet.update`, `bulk_create`, or raw SQL for operational
RBAC changes: these bypass model validation/signals. Use the supported APIs/Admin. Model-level
database constraints still prevent duplicate links. Cross-table policy needs the service layer.

## Auditing, indexes, and performance

Signals capture relevant role, mapping, group, permission, user-status and native membership
changes, including Admin operations. A request-scoped ContextVar attaches the session/JWT
actor. Rows contain action, entity, ID, timestamp, and before/after fields. Passwords, tokens,
email and request bodies are excluded. User/group direct membership clear operations record
removed IDs. Trusted seed/CLI/migration changes can have a null actor. API/Admin transactions
roll audit writes back with failed mutations. The audit API/Admin are read-only. Production
operators should export audit records to immutable storage and enforce retention; a DB owner
can still edit the database. Audit records are evidence, not cryptographic tamper protection.

Foreign keys automatically supply PostgreSQL indexes. Composite unique constraints on
`(user_id, role_id)` and `(role_id, permission_id)` enforce link uniqueness and speed joins.
Role name/code have unique indexes plus case-insensitive expression constraints using LOWER.
The ordinary name/code unique indexes are retained for Django validation; expression indexes
enforce the case-insensitive database guarantee. Audit uses a timestamp index for retention
and `(entity, entity_id)` for investigations. Boolean role flags are not indexed independently:
their low selectivity rarely justifies it. Revisit query plans with actual production cardinality.
Role lists prefetch permissions, mapping/Admin lists select related objects, and effective access
uses a set-valued single query. List endpoints paginate at 25 records and expose controlled filters.
A regression test bounds role-list SELECT counts to catch N+1 behavior.

## Testing and quality

```sh
ruff check .
ruff format --check .
python manage.py check
python manage.py makemigrations --check --dry-run
pytest
python manage.py spectacular --file docs/openapi.yml --validate --fail-on-warn
docker build -t cloud9-rbac:local .
```

Pytest selects `config.settings.test` automatically and defaults to PostgreSQL. For a limited
environment, `TEST_SQLITE=1 pytest` (PowerShell: `$env:TEST_SQLITE='1'; pytest`) runs SQLite
tests; it does not verify production locking or a PostgreSQL installation. Tests cover model
constraints, merged grants, source-by-source revocation, JWT rotation/blacklisting, inactive
accounts, protected business CRUD, self-escalation, manipulated Admin requests, native Admin
audit changes, custom permission protections, CSRF, pagination and query bounds.
See the verification report for actual local results rather than inferred CI success.

## Git workflow and CI/CD

Initialize/import this folder into your GitHub repository. Create `main` and optionally `develop`,
work on `feature/<description>` branches, commit meaningful changes and migration files, and
open a pull request. Require the `CI / verify` check and review before merge; protect main against
direct pushes. Never commit `.env`, databases, virtual environments, secrets, or collected static files.

CI runs on PRs and pushes to main/develop, installs pinned dependencies, checks Ruff lint/format,
Django checks, missing migrations, fresh PostgreSQL migrations, the full test suite, schema validation,
and a Docker image build. Coverage/schema are retained as workflow artifacts.

The separate manually triggered deployment workflow runs only from the `main` branch and requires a successful CI run for the exact commit. The deployment workflow uses a secure Render Deploy Hook stored as a GitHub Actions secret (`RENDER_DEPLOY_HOOK`) to trigger the production deployment.

After triggering the deployment, GitHub Actions waits for the Render service to start and verifies the production `/health/` endpoint. The application is deployed as a Docker-based Render Web Service and uses Render PostgreSQL as the production database.

### Rollback

If a production deployment causes an issue, open the Render dashboard and select the `cloud9-rbac` Web Service. Use the deployment history to redeploy a previously working deployment. Alternatively, revert the problematic Git commit, push the corrected state to `main`, allow CI to complete successfully, and run the `Deploy complete application` GitHub Actions workflow again. After rollback, verify `/health/` and `/ready/` before considering the application restored.

## Dependencies and maintenance

Django/DRF provide ORM, native auth, Admin and REST; SimpleJWT supplies short-lived API tokens and
refresh blacklisting; django-filter handles validated filters; psycopg is PostgreSQL's driver;
Gunicorn serves WSGI; WhiteNoise serves collected static assets; drf-spectacular produces validated
OpenAPI; python-dotenv supports local environment files. Pytest/pytest-django/coverage and Ruff are
development-only. Transitive versions are pinned in requirements files; `.in` files document direct
dependency ranges. Review upgrades regularly, regenerate pins, and rerun PostgreSQL CI and image
build before deploying. Container base tags are moving patch tags: pin organization-approved digests
for bit-for-bit release builds and refresh them for security fixes.

DRF's in-process throttles are a basic abuse control, not distributed rate limiting or brute-force
protection. Enforce login/API rate limits at the TLS gateway across all workers, and protect Admin
with organization access controls/MFA at that gateway. Logout blacklists the refresh token; an
already-issued access token lives for at most five minutes. Authorization is always re-read from DB.

References: [Django 5.2 releases](https://docs.djangoproject.com/en/5.2/releases/),
[Django authentication customization](https://docs.djangoproject.com/en/5.2/topics/auth/customizing/),
[DRF permissions](https://www.django-rest-framework.org/api-guide/permissions/).
