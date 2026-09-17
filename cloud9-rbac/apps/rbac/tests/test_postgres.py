import pytest
from django.contrib.auth.models import Permission
from django.db import DatabaseError, connection, transaction

from apps.rbac.models import Role
from apps.rbac.services import lock_administration


@pytest.mark.django_db
def test_case_insensitive_uniqueness_is_database_enforced():
    Role.objects.create(name="Unique", code="unique")
    with pytest.raises(DatabaseError), transaction.atomic():
        Role.objects.bulk_create([Role(name="UNIQUE", code="different")])


@pytest.mark.django_db(transaction=True)
def test_postgres_administration_lock_excludes_second_writer():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock semantics require PostgreSQL; CI executes this test.")
    import psycopg

    permission = Permission.objects.get(codename="manage_rbac")
    params = connection.get_connection_params()
    with transaction.atomic():
        lock_administration()
        with psycopg.connect(**params) as second:
            with pytest.raises(psycopg.errors.LockNotAvailable):
                second.execute(
                    "SELECT id FROM auth_permission WHERE id = %s FOR UPDATE NOWAIT",
                    (permission.pk,),
                )
