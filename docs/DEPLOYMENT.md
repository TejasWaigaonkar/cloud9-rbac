# Production deployment: Linux Docker host + managed PostgreSQL

This is a runnable deployment template, not an already deployed service. Provision an Ubuntu
host with Docker Engine/Compose v2, HTTPS reverse proxy (Nginx/Caddy), and a managed PostgreSQL 17
database reachable privately. Restrict inbound traffic to HTTPS and deployment SSH. RBAC and
projects share the same container release and database. CI must pass before first deployment.

## One-time host provisioning

1. Create a dedicated deployment account with the required Docker permissions (Docker group access
   is effectively host-root authority). Install its SSH public key. Keep its private key in GitHub.
2. Create `/opt/cloud9`, owned by that account. Copy `deploy/compose.prod.yml` there as
   `compose.prod.yml` and `deploy/deploy.sh` as `deploy.sh`; run `chmod 750 /opt/cloud9/deploy.sh`.
3. Create `/opt/cloud9/app.env`, mode 600. Fill the production settings below using real secrets:

   ```dotenv
   DJANGO_SETTINGS_MODULE=config.settings.prod
   DJANGO_SECRET_KEY=<random-50-plus-character-secret>
   DJANGO_ALLOWED_HOSTS=rbac.example.com,127.0.0.1
   CSRF_TRUSTED_ORIGINS=https://rbac.example.com
   TRUST_PROXY_PROTO=1
   POSTGRES_DB=cloud9
   POSTGRES_USER=cloud9
   POSTGRES_PASSWORD=<database-secret>
   POSTGRES_HOST=<private-managed-database-host>
   POSTGRES_PORT=5432
   PGSSLMODE=verify-full
   PGSSLROOTCERT=/etc/ssl/certs/ca-certificates.crt
   ```

   Use a CA bundle trusted for the database provider; mount a provider CA when required.
   PGSSLMODE/PGSSLROOTCERT are libpq environment variables used by psycopg.
4. Create `/opt/cloud9/host.env`, mode 600, with `APP_HOST=rbac.example.com` for the smoke check.
5. Point a TLS reverse proxy to `127.0.0.1:8000`. Preserve Host and **overwrite**
   `X-Forwarded-Proto` with the actual client protocol. Do not expose port 8000 publicly.
   Configure HTTPS certificates, distributed login/API rate limits and Admin access controls.
6. Configure host GHCR read access for a private image using a separate read-only package token:
   `docker login ghcr.io`. The workflow's temporary publishing token is not persisted on the host.
7. Enable managed database backups/PITR and verify a restore into staging. Keep a pre-release
   snapshot before schema changes. Size connection limits for workers and scaling.

## GitHub settings

Create a `production` environment with required reviewer approval. Configure environment secrets:

| Secret | Value |
| --- | --- |
| DEPLOY_HOST | Provisioned host DNS/IP |
| DEPLOY_USER | Dedicated SSH deployment account |
| DEPLOY_SSH_KEY | Private key for that account |
| DEPLOY_KNOWN_HOSTS | Host's SSH public host-key line, verified out of band |

`GITHUB_TOKEN` is supplied by GitHub for GHCR push and CI-status lookup. Enable packages write
permission for the deployment workflow. Do not use unverified `ssh-keyscan` during deployments.
Application/database secrets remain on the host or in a secrets manager.

## Release

Merge a reviewed PR to main and wait for CI success. Manually run **Deploy complete application**
on main and approve the protected environment. The workflow verifies successful CI for the exact
commit, builds/pushes `ghcr.io/<owner>/<repo>:<commit-sha>`, and invokes the host script. The script:

1. Pulls the exact image tag.
2. Runs production Django deployment checks, failing on warnings.
3. Runs migrations once in a one-off container.
4. Replaces the whole application and waits for its liveness check.
5. Probes database readiness and records the deployed image.

This single-host template can have brief downtime and does not promise zero-downtime rollout.
Use backward-compatible expand/contract migrations because old workers may briefly coexist with
the new schema. Never run destructive migrations without a reviewed maintenance/restore plan.

Bootstrap the first superuser interactively after setting APP_IMAGE in the host shell:

```sh
cd /opt/cloud9
export APP_IMAGE=ghcr.io/YOUR_OWNER/YOUR_REPOSITORY:YOUR_COMMIT_SHA
docker compose -f compose.prod.yml run --rm web python manage.py createsuperuser
```

Check HTTPS `/health/`, `/ready/`, Admin login, and an authenticated allowed/denied projects
request after deployment. Watch logs and error rates. Add uptime alerts, database/storage alerts,
audit-log export and retention. Schedule `flushexpiredtokens` daily in the deployment environment
to clean expired SimpleJWT blacklist data.

## Rollback

Record the previous immutable image tag before deployment. If the new application fails but
schema changes are backward compatible, run `/opt/cloud9/deploy.sh <previous-image-tag>`.
This does not reverse migrations: applied migrations remain recorded. For incompatible schema
changes, restore the verified database backup and previous application in a maintenance window,
or apply a reviewed forward fix. Do not blindly reverse migrations or automatically restore a
production database. If migration/check steps fail, the script exits before replacing the service.
If readiness fails after replacement, inspect logs and explicitly roll back using this procedure.

Pin base images/action versions to organization-approved digests/commit SHAs for hardened supply
chain policy. Refresh dependency pins and images regularly; do not treat an old verified build as
permanently secure. Audit rows are application-read-only; export them off-host for tamper evidence.
