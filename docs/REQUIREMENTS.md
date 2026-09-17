# Assignment traceability

Source: six-page Cloud9Space_RBAC_Intern_Assignment (Revised).pdf attached to the referenced
conversation. Groups via native Django Admin are explicitly allowed on pages 2 and 4.

| PDF requirement | Implementation / evidence |
| --- | --- |
| Single application/repository/deployment | config + apps/rbac, apps/users, apps/projects; one Docker image |
| Native User/Group/Permission and mappings | django.contrib.auth; hardened native UserAdmin/GroupAdmin |
| Dynamic roles, metadata and flags | Role; no role-name conditions in authorization |
| Explicit mappings and unique constraints | UserRole, RolePermission; initial migration |
| Controlled permission CRUD and stable codes | PermissionViewSet, custom_ namespace, immutable declared/generated permissions |
| Role CRUD, deactivation, system protection | RoleViewSet, model checks, Admin policy, tests |
| Assign and revoke multiple roles | UserAccessViewSet; self-assignment prohibited |
| Effective grants from three sources | RBACBackend DISTINCT query; source-by-source revocation tests |
| Django authorization integration | ModelBackend subclass; has_perm/has_perms/has_module_perms preserved |
| Reusable DRF checks | StrictModelPermissions; explicit view checks and publish action |
| JWT/session authentication | SimpleJWT rotating blacklist + SessionAuthentication/CSRF |
| Admin including native group changes | Superuser-only native Admin; m2m audit signals |
| Audit actor/action/entity/time/before-after | AuditLog + ContextVar + signals; API/Admin tests |
| Privilege escalation prevention | Owned-grant delegation, no self/own-role edits, native Admin restrictions |
| Mandatory manipulated Admin test | test_manipulated_admin_post_blocked_for_staff (six routes) |
| Validation and consistent errors | Serializers, model/DB constraints, shared exception handler |
| Pagination/filtering/query optimization | 25-item pagination, explicit filters, prefetch/select_related, query-bound test |
| Environment separation/no secrets | dev/test/prod settings, empty-secret .env.example, ignored .env |
| Seed users/groups/roles/permissions | Idempotent seed_demo, unusable passwords, production refusal |
| Comprehensive model/API/security tests | Per-app tests packages and verification report |
| PostgreSQL migrations/index discussion | Committed initial migrations; README indexes; fresh DB CI job |
| Dockerfile + persistent Compose | Multi-stage/nonroot Dockerfile; postgres_data volume |
| Health/readiness | /health/ and /ready/, 503 fallback tested |
| CI lint/format/tests/migrations/image build | .github/workflows/ci.yml |
| Separate deployment workflow | deploy.yml, GHCR/SSH, protected environment, deployment runbook |
| README/API examples/Postman | README, docs/API.md, OpenAPI and Postman assets |
| Git branching/PR practice | README; GitHub branch protections configured by repository owner |
| Submission evidence | Local report included; remote CI URL and deployment URL require actual publishing |

No GitHub repository, CI run, or hosted deployment is claimed to exist. The deliverable is the
complete repository archive; publishing and infrastructure execution are documented next steps.
