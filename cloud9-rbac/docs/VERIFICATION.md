# Local verification report

Verified on 2026-09-16 on Windows, Python 3.13.7, Django 5.2.17.
This report describes executed checks, not a claim that remote CI or deployment has run.

| Check | Result |
| --- | --- |
| Application tests against freshly migrated SQLite test DB | **60 passed, 1 skipped** |
| Application code coverage (excluding tests/migrations) | **97%**, 607 of 624 statements |
| PostgreSQL two-connection locking test | Skipped locally; enabled automatically against PostgreSQL in CI |
| Ruff lint | Passed |
| Ruff format | Passed, 51 Python files already formatted |
| Django system check | Passed, zero issues |
| Migration drift: makemigrations --check --dry-run | Passed, no changes detected |
| Fresh empty SQLite migration + demo seed twice | Passed, two accounts, no usable default passwords |
| Production check --deploy --fail-level WARNING | Passed with ephemeral environment secrets and explicit HTTPS configuration |
| OpenAPI generation/validation with --fail-on-warn | Passed |
| Production-compatible static collection | Passed; WhiteNoise manifest created |
| JSON/Postman and YAML parsing | Passed |
| PostgreSQL migration/runtime verification | Not run: no local PostgreSQL server available |
| Docker image build/Compose startup | Not run: Docker unavailable on this host |
| GitHub Actions execution | Not run: no remote repository was created or workflow dispatched |
| Production deployment | Not run: no infrastructure/secrets supplied |

The suite includes manipulated Admin requests against six administration routes even after granting
the staff account native Django model permissions; all are denied. Additional tests cover normal
nonstaff Admin access, self-role assignment, own-role mutation, system roles, delegated grants,
three-source permission union and final-source revocation, CSRF, JWT refresh rotation/logout,
immediate permission revocation with an existing JWT, custom permission protection, native Admin
user/group membership auditing, role deactivation, database uniqueness, and bounded list queries.

For local reproduction with installed requirements: set `TEST_SQLITE=1`, then run `pytest`.
For full verification, leave TEST_SQLITE unset and use PostgreSQL as documented in README.
The CI workflow applies migrations to a fresh PostgreSQL 17 service, executes the PostgreSQL-only
lock test, validates the schema, and builds the production Docker image. Do not claim those checks
passed until an actual CI run is green. A hosted URL and successful CI URL are submission evidence
to add after publishing this repository and deploying it.

Production configuration checks validate settings, not live TLS, database access, backup/restore,
load behavior, host provisioning, or gateway rate limiting. Follow the deployment runbook and test
those operational requirements in staging before a real production launch.
