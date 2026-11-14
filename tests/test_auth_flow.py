"""
Authentication flow tests for the Streamlit application.

Uses Streamlit's official AppTest harness with a FAKE Supabase client, so the
real login/gating/session logic is executed without any network calls and
without real credentials. A live-Supabase variant lives in
tests/test_supabase_auth_integration.py and only runs when real (test)
credentials are explicitly provided.
"""
import time
import types
from pathlib import Path

import pytest

from streamlit.testing.v1 import AppTest

from tests.conftest import CAMP_A, STAFF_A

REPO = Path(__file__).resolve().parents[1]
REPO_EMAIL = "staffa@example.test"
REPO_PASSWORD = "synthetic-test-password"


class _FakeQuery:
    def __init__(self, data):
        self._data = data

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def single(self):
        return self

    def execute(self):
        return types.SimpleNamespace(data=self._data)


class _FakeAuth:
    def __init__(self):
        self.signed_in = False

    def sign_in_with_password(self, creds):
        if creds.get("password") != REPO_PASSWORD:
            raise Exception("invalid credentials (fake)")
        self.signed_in = True
        user = types.SimpleNamespace(id=STAFF_A, email=creds.get("email"))
        session = types.SimpleNamespace(
            access_token="fake-access-token",
            refresh_token="fake-refresh-token",
            expires_at=int(time.time()) + 3600,
            user=user,
        )
        return types.SimpleNamespace(session=session, user=user)

    def sign_out(self):
        self.signed_in = False

    def set_session(self, access, refresh):
        return None

    def refresh_session(self, refresh):
        raise RuntimeError("fake client does not refresh")


class _FakeClient:
    def __init__(self, url="", key=""):
        self.auth = _FakeAuth()

    def table(self, name):
        if name == "profiles":
            return _FakeQuery([{"role": "camp_staff", "camp_id": CAMP_A}])
        if name == "camps":
            return _FakeQuery([{"name": "Synthetic Camp A"}])
        return _FakeQuery([])


@pytest.fixture()
def app(monkeypatch):
    """AppTest with authentication forced on and a fake Supabase client."""
    import auth.supabase_auth as sa

    monkeypatch.setenv("AUTH_REQUIRED", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "fake-public-anon-key")
    monkeypatch.setattr(sa, "_make_client", lambda url, key: _FakeClient(url, key))

    at = AppTest.from_file(str(REPO / "app.py"), default_timeout=60)
    at.run()
    return at


def _submit_login(at, email, password):
    text_inputs = list(at.text_input)
    assert len(text_inputs) >= 2, "login form (email + password) not rendered"
    text_inputs[0].set_value(email)
    text_inputs[1].set_value(password)
    submits = [b for b in at.button if "Sign In" in (b.label or "")]
    assert submits, "Sign In button not found"
    submits[0].click()
    at.run()


def test_login_page_blocks_the_application(app):
    # Login screen is shown, the application views are not
    assert any("Staff Sign In" in t.value for t in app.title)
    assert not app.sidebar.radio, "app views must not render before sign-in"


def test_successful_login_and_logout(app):
    _submit_login(app, REPO_EMAIL, REPO_PASSWORD)

    # Signed in: sidebar identity + application views available.
    # (The auth context lives in a thread-local set by the app's own script
    # thread under AppTest, so it is verified through the rendered UI here.)
    assert app.sidebar.radio, "application views must render after sign-in"
    sidebar_text = " ".join(m.value for m in app.sidebar.markdown)
    assert REPO_EMAIL in sidebar_text
    assert "Camp Staff" in sidebar_text

    # Log out
    logout = [b for b in app.sidebar.button if "Sign Out" in (b.label or "")]
    assert logout, "Sign Out button missing"
    logout[0].click()
    app.run()

    assert any("Staff Sign In" in t.value for t in app.title)
    assert not app.sidebar.radio


def test_wrong_password_is_rejected(app):
    from database.context import get_auth_context

    _submit_login(app, REPO_EMAIL, "definitely-wrong")
    assert any("Staff Sign In" in t.value for t in app.title)
    errors = [e.value for e in app.error]
    assert errors and any("Sign-in failed" in e for e in errors)
    assert get_auth_context() == {}
    assert not app.sidebar.radio
