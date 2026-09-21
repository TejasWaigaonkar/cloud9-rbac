# Deployment guide

The application includes an optional Render deployment workflow. Local development uses Docker Compose with Django and PostgreSQL.

## Target platform

- Render Web Service using the repository's Dockerfile.
- Render PostgreSQL database.
- Django, RBAC, and the projects application are deployed together.

The files in `deploy/` provide an alternative self-managed Docker-host setup. They are not used by the current GitHub Actions workflow.

## Render configuration

1. Create a Render PostgreSQL database.
2. Create a Docker-based Render Web Service connected to this repository's `main` branch.
3. Configure the application environment variables:

| Variable | Value |
| --- | --- |
| DJANGO_SETTINGS_MODULE | config.settings.prod |
| DJANGO_SECRET_KEY | A private, randomly generated secret of at least 50 characters |
| DJANGO_ALLOWED_HOSTS | The service hostname, without https:// |
| CSRF_TRUSTED_ORIGINS | The full HTTPS service URL |
| TRUST_PROXY_PROTO | 1 when using Render's trusted HTTPS proxy |
| POSTGRES_DB | Render database name |
| POSTGRES_USER | Render database username |
| POSTGRES_PASSWORD | Render database password |
| POSTGRES_HOST | Render database internal hostname |
| POSTGRES_PORT | 5432 |

Store values in Render's environment settings. Never commit passwords, secrets, or a populated `.env` file.

Ensure the startup command runs Django migrations before starting Gunicorn. Use `/health/` as the service health-check path.

Disable automatic deploys if releases should happen only through the GitHub deployment workflow.

## GitHub configuration

1. Create a GitHub environment named `production`.
2. Obtain the web service's Deploy Hook from Render.
3. Add it as the GitHub Actions secret `RENDER_DEPLOY_HOOK`.
4. Configure environment approval rules if required.

The deploy hook is a secret and must not be placed in source code or documentation.

## Deployment workflow

1. Merge a reviewed pull request into `main`.
2. Wait for CI to pass for that commit.
3. Open GitHub Actions.
4. Select **Deploy complete application**.
5. Run the workflow on `main`.

The workflow checks for successful CI, calls the Render deploy hook, waits, and checks the public `/health/` endpoint.

If using a different Render service, update the health-check URL in `.github/workflows/deploy.yml`.

A successful health response alone does not prove that the intended new revision is deployed. Confirm the deployed commit and deployment status in Render.

## Verification

After deployment, check:

- `/health/` returns `{"status":"ok"}`.
- `/ready/` returns `{"status":"ready"}`.
- Authenticated API requests allow permitted operations and reject forbidden operations.

Render uses a separate database from local Docker. Local accounts are not automatically copied to it.

## Rollback

Use Render's deployment history to roll back when supported, or revert the problematic Git commit through a pull request and redeploy after CI passes.

Application rollback does not automatically reverse database migrations. Use backward-compatible migrations and maintain database backups. Incompatible database changes need a reviewed recovery plan.

After rollback, check `/health/`, `/ready/`, and authenticated API behavior.

## Assignment submission

Include the repository URL, successful CI-run link, architecture documentation, and API documentation/Postman collection.

Include a deployment URL if submitting a deployed instance. Continuing to operate a live service is not necessary for demonstrating the local Docker setup and supplying the deployment workflow.
