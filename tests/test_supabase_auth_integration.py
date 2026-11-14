"""
Live Supabase Auth integration test — SKIPPED unless real (test) credentials
are explicitly provided via environment variables.

    SUPABASE_URL            e.g. https://xxxx.supabase.co
    SUPABASE_ANON_KEY       public anon key
    SUPABASE_TEST_EMAIL     an email registered in that project's Auth
    SUPABASE_TEST_PASSWORD  its password

These variables are never set by default; the whole module skips otherwise.
No production credentials, no real patient data. This is the ONLY test that
contacts a real Supabase project, and only when you opt in.
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    not all(os.getenv(k) for k in (
        "SUPABASE_URL", "SUPABASE_ANON_KEY",
        "SUPABASE_TEST_EMAIL", "SUPABASE_TEST_PASSWORD")),
    reason="Live Supabase Auth credentials not provided "
           "(set SUPABASE_URL / SUPABASE_ANON_KEY / "
           "SUPABASE_TEST_EMAIL / SUPABASE_TEST_PASSWORD to run)",
)


def test_sign_in_and_sign_out_roundtrip():
    import auth.supabase_auth as sa

    client = sa.get_client()
    ok, message = sa.sign_in(
        os.environ["SUPABASE_TEST_EMAIL"],
        os.environ["SUPABASE_TEST_PASSWORD"],
    )
    assert ok, f"sign_in failed: {message}"

    # Profile row exists (created by the handle_new_user trigger)
    user_id = sa.ensure_auth().get("user_id")
    assert user_id, "ensure_auth must resolve the signed-in user"
    res = (
        client.table("profiles")
        .select("role")
        .eq("user_id", user_id)
        .execute()
    )
    assert res.data and res.data[0]["role"] in ("camp_staff", "admin")

    sa.sign_out()
    # After sign-out there must be no usable session
    try:
        current = client.auth.get_session()
    except Exception:
        current = None
    assert current is None
