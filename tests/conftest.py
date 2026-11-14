"""
Pytest configuration for Phase 1 cloud-preparation tests.

All PostgreSQL tests run against a LOCAL Docker PostgreSQL that mimics
Supabase (roles + auth.uid() stub — see tests/local_supabase_stub.sql and
tests/start_local_pg.ps1). They are SKIPPED when that database is not
reachable, so no test ever talks to a real Supabase project.

Synthetic patient records only. The real SQLite database is never written.
"""
import json
import os
import uuid
from pathlib import Path

import pytest

# --- Environment must be set BEFORE database.db is imported -----------------
os.environ["DB_BACKEND"] = "postgres"
os.environ["SUPABASE_DB_URL"] = "postgresql://postgres:postgres@127.0.0.1:5433/postgres"
os.environ["SUPABASE_DB_SSLMODE"] = "prefer"
os.environ.pop("SUPABASE_DB_ADMIN_MODE", None)
os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_ANON_KEY", None)

REPO_ROOT = Path(__file__).resolve().parents[1]

# Synthetic identities (fixed UUIDs keep assertions deterministic)
CAMP_A = "11111111-1111-4111-8111-111111111111"
CAMP_B = "22222222-2222-4222-8222-222222222222"
STAFF_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
STAFF_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
ADMIN_ALL = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"


def _pg_available() -> bool:
    try:
        import psycopg
        from database.pg import _dsn_from_env
        dsn = _dsn_from_env().split("?")[0]
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select 1 from information_schema.tables "
                    "where table_schema='public' and table_name='feedback_sessions'")
                return cur.fetchone() is not None
    except Exception:
        return False


PG_AVAILABLE = _pg_available()

requires_pg = pytest.mark.skipif(
    not PG_AVAILABLE,
    reason="Local test PostgreSQL not reachable (run tests/start_local_pg.ps1 "
           "and apply supabase/migrations/)",
)


@pytest.fixture(scope="session")
def admin_conn():
    """Administrative (RLS-bypassing) connection used to seed synthetic data."""
    if not PG_AVAILABLE:
        pytest.skip("local PostgreSQL unavailable")
    from database.pg import connect
    conn = connect(admin=True)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def seeded_identities(admin_conn):
    """Create two camps and three users (2 staff + 1 admin) with profiles."""
    if not PG_AVAILABLE:
        pytest.skip("local PostgreSQL unavailable")

    cursor = admin_conn.cursor()
    for camp_id, name in ((CAMP_A, "Synthetic Camp A"), (CAMP_B, "Synthetic Camp B")):
        cursor.execute(
            "insert into public.camps (id, name) values (%s, %s) on conflict (id) do nothing",
            (camp_id, name))
    users = [
        (STAFF_A, "staffa@example.test", {"role": "camp_staff", "camp_id": CAMP_A}),
        (STAFF_B, "staffb@example.test", {"role": "camp_staff", "camp_id": CAMP_B}),
        (ADMIN_ALL, "admin@example.test", {"role": "admin", "camp_id": ""}),
    ]
    for user_id, email, meta in users:
        cursor.execute(
            "insert into auth.users (id, email, raw_user_meta_data) "
            "values (%s, %s, %s::jsonb) on conflict (id) do nothing",
            (user_id, email, json.dumps(meta)))
    admin_conn.commit()

    # Profiles must exist (created by the handle_new_user trigger)
    cursor.execute("select count(*) from public.profiles where user_id = any(%s)",
                   ([u[0] for u in users],))
    assert cursor.fetchone()[0] == 3, "profile trigger did not create profiles"
    return {"camps": (CAMP_A, CAMP_B),
            "staff_a": STAFF_A, "staff_b": STAFF_B, "admin": ADMIN_ALL}


@pytest.fixture()
def as_staff_a(seeded_identities):
    from database.context import set_auth_context, clear_auth_context
    set_auth_context(user_id=STAFF_A, camp_id=CAMP_A, role="camp_staff")
    yield
    clear_auth_context()


@pytest.fixture()
def as_staff_b(seeded_identities):
    from database.context import set_auth_context, clear_auth_context
    set_auth_context(user_id=STAFF_B, camp_id=CAMP_B, role="camp_staff")
    yield
    clear_auth_context()


@pytest.fixture()
def as_admin(seeded_identities):
    from database.context import set_auth_context, clear_auth_context
    set_auth_context(user_id=ADMIN_ALL, camp_id=None, role="admin")
    yield
    clear_auth_context()


@pytest.fixture(autouse=True)
def _clean_context():
    from database.context import clear_auth_context
    clear_auth_context()
    yield
    clear_auth_context()


@pytest.fixture()
def sqlite_env(tmp_path, monkeypatch):
    """Switch the active backend to SQLite on a TEMPORARY database file."""
    import database.db as db
    monkeypatch.setattr(db, "_BACKEND", "sqlite")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    yield tmp_path
