# API guide

All routes use trailing slashes. JSON request bodies use `Content-Type: application/json`.
Success responses use resource objects, or `{count,next,previous,results}` for paginated lists.
Failures use `{"error":{"status":403,"details":{"detail":"..."}}}`. Validation details can
be field maps or arrays. Expected statuses: 200 read/update, 201 create/map/assign, 204 delete,
400 invalid/duplicate/inactive/in-use, 401 missing/invalid JWT, 403 insufficient rights/CSRF,
404 unknown object, 405 unsupported method, 429 throttled. Health uses its own simple envelope.

## Authentication

```sh
curl -X POST http://localhost:8000/api/auth/token/   -H 'Content-Type: application/json'   -d '{"username":"YOUR_USER","password":"YOUR_LOCAL_PASSWORD"}'
```

Returns `{"access":"...","refresh":"..."}`. Use `Authorization: Bearer <access>` thereafter.
POST `/api/auth/refresh/` with `{"refresh":"..."}` rotates and blacklists the old refresh token.
POST `/api/auth/logout/` with that refresh token blacklists it. Access tokens expire after five
minutes; refresh tokens after eight hours. Session authentication also works with CSRF tokens on
unsafe requests; log into Admin for the browsable API and interactive `/api/docs/`.

## RBAC administration

The following APIs require `rbac.manage_rbac`; additional mutation restrictions are in README.

| Method and path | Body / behavior |
| --- | --- |
| GET, POST `/api/roles/` | List/create; `{ "name":"Reviewer", "code":"reviewer", "description":"Reviews projects" }` |
| GET, PUT, PATCH, DELETE `/api/roles/{id}/` | Read/update/delete; deactivate with `{ "is_active":false }` |
| POST `/api/roles/{id}/permissions/` | `{ "permission_id":53 }` |
| DELETE `/api/roles/{id}/permissions/{permission_id}/` | Remove one mapping |
| GET, POST `/api/permissions/` | List/create custom; `{ "name":"Export projects", "codename":"custom_export" }` |
| GET, PUT, PATCH, DELETE `/api/permissions/{id}/` | Custom display-name update or unused custom delete |
| POST `/api/users/{id}/roles/` | `{ "role_id":1 }`; target must be someone else |
| DELETE `/api/users/{id}/roles/{role_id}/` | Revoke assignment |
| GET `/api/users/{id}/roles/` | Paginated roles, including inactive roles |
| GET `/api/users/{id}/permissions/` | Roles, groups and effective permission codes |
| GET `/api/audit-logs/` | Read-only audit evidence |

User access endpoints also allow a normal authenticated user to read their **own** access only.
Discover permission/user/role IDs from your database; never assume generated primary keys.
Users and native groups are created/managed at `/admin/auth/user/` and `/admin/auth/group/`.
Role output includes `permission_ids`; mapping operations return their link ID plus permission/role ID.
Permission output includes numeric content type and stable `code` such as `projects.view_project`.

Filters: roles `?search=review&is_active=true&is_system=false&code=reviewer&ordering=name&page=1`;
permissions `?content_type__app_label=projects&codename=view_project&search=view&ordering=codename`;
audit `?entity=rbac.role&entity_id=1&actor=1&action=update`. Page size is 25.

Effective access example:

```json
{
  "user_id": 2,
  "is_active": true,
  "roles": [{"role_id": 1, "role__code": "reviewer", "role__is_active": true}],
  "groups": [{"id": 1, "name": "Project Readers"}],
  "permissions": ["projects.view_project"]
}
```

## Protected projects

| Method/path | Required permission |
| --- | --- |
| GET `/api/projects/` or `/api/projects/{id}/` | `projects.view_project` |
| POST `/api/projects/` | `projects.add_project` |
| PUT/PATCH `/api/projects/{id}/` | `projects.change_project` |
| DELETE `/api/projects/{id}/` | `projects.delete_project` |
| POST `/api/projects/{id}/publish/` | `projects.publish_project` |

Create body: `{"name":"First project","description":"Example"}`. `published` is read-only
outside the publish operation. List filters include `search`, `published`, `ordering`, and `page`.
The protected-operation identifiers are model-declared and cannot be modified at runtime.
For a new operation, declare its permission in model Meta, migrate, and add it to the view's
`action_permissions`; runtime permission records alone do not create behavior.

## End-to-end verification

1. Bootstrap root, seed demo, and set demo passwords as in README.
2. Login as root and list project permissions; create a role and map `projects.view_project`.
3. Find a different user's ID in Admin; assign the role through the user-role API.
4. Login as that user: GET projects returns 200; DELETE a project returns 403.
5. Root deactivates the role. GET now returns 403 unless a group or direct grant still exists.
6. Grant view via a native group. GET returns 200. Remove the final source; GET returns 403.
7. A normal user's role-create or self-role-assignment request returns 403; manipulated Admin
   POSTs cannot add grants. Inspect read-only audit logs as root.

## Documentation and tooling

Import `cloud9.postman_collection.json` and `cloud9.postman_environment.json`. Set local-only
`username`, `password`, `target_user_id`, and discovered IDs. The Login request saves access/refresh
tokens to your local environment; do not export or share populated environment secrets.
The collection includes positive and negative test scripts and assignment/mapping requests.
`/api/schema/` serves OpenAPI and `/api/docs/` provides Swagger, both authenticated.
`GET /health/` is database-independent; `GET /ready/` executes SELECT 1 and returns 503 on failure.
Neither health endpoint discloses connection details.
