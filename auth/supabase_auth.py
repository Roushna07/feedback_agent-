"""
Supabase Auth integration for the Streamlit application.

Signs staff in with email/password (Supabase Auth), loads their profile
(role + authorized camp) and stamps database/context so every PostgreSQL
query runs under the user's JWT — Row Level Security is enforced by the
database, not by hiding Streamlit pages.

Secrets come from `.streamlit/secrets.toml` (Streamlit Community Cloud) or
environment variables (local). Nothing here is ever hard-coded.
"""
import os
import time
from typing import Any, Dict, Optional, Tuple

import streamlit as st

from database.context import (
    DEFAULT_CAMP_ID,
    clear_auth_context,
    set_auth_context,
)

# session_state keys
_K_ACCESS = "sb_access_token"
_K_REFRESH = "sb_refresh_token"
_K_EXPIRES = "sb_expires_at"
_K_USER_ID = "sb_user_id"
_K_EMAIL = "sb_user_email"
_K_ROLE = "sb_role"
_K_CAMP = "sb_camp_id"
_K_CAMP_NAME = "sb_camp_name"


def _setting(env_name: str, secret_key: str) -> str:
    """Read a setting from st.secrets first, then from the environment."""
    try:
        secrets = st.secrets  # may raise when no secrets.toml exists
        if secret_key in secrets:
            val = str(secrets[secret_key]).strip()
            if val:
                return val
    except Exception:
        pass
    return os.getenv(env_name, "").strip()


def supabase_configured() -> Tuple[bool, str]:
    url = _setting("SUPABASE_URL", "SUPABASE_URL")
    key = _setting("SUPABASE_ANON_KEY", "SUPABASE_ANON_KEY")
    if not url or not key:
        return False, "SUPABASE_URL / SUPABASE_ANON_KEY are not configured."
    return True, ""


def auth_required() -> bool:
    """Authentication is mandatory exactly when the app uses PostgreSQL."""
    from database.db import get_backend
    if get_backend() == "postgres":
        return True
    return os.getenv("AUTH_REQUIRED", "").strip() == "1"


@st.cache_resource(show_spinner=False)
def _make_client(url: str, key: str):
    from supabase import create_client
    return create_client(url, key)


def get_client():
    ok, err = supabase_configured()
    if not ok:
        raise RuntimeError(err)
    return _make_client(
        _setting("SUPABASE_URL", "SUPABASE_URL"),
        _setting("SUPABASE_ANON_KEY", "SUPABASE_ANON_KEY"),
    )


def _store_session(session: Any, user: Any = None) -> None:
    st.session_state[_K_ACCESS] = session.access_token
    st.session_state[_K_REFRESH] = session.refresh_token
    st.session_state[_K_EXPIRES] = int(getattr(session, "expires_at", 0) or 0)
    if user is not None:
        st.session_state[_K_USER_ID] = user.id
        st.session_state[_K_EMAIL] = getattr(user, "email", None)
    elif getattr(session, "user", None) is not None:
        st.session_state[_K_USER_ID] = session.user.id
        st.session_state[_K_EMAIL] = getattr(session.user, "email", None)


def _load_profile(client, user_id: str) -> Optional[Dict[str, Any]]:
    try:
        res = client.table("profiles").select("role, camp_id").eq("user_id", user_id).execute()
        rows = res.data or []
        return rows[0] if rows else None
    except Exception:
        return None


def _load_camp_name(client, camp_id: Optional[str]) -> Optional[str]:
    if not camp_id:
        return None
    try:
        res = client.table("camps").select("name").eq("id", camp_id).execute()
        rows = res.data or []
        return rows[0]["name"] if rows else None
    except Exception:
        return None


def sign_in(email: str, password: str) -> Tuple[bool, str]:
    """Authenticate against Supabase Auth. Returns (success, error message)."""
    try:
        client = get_client()
    except Exception as exc:
        return False, str(exc)
    try:
        res = client.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:
        return False, "Sign-in failed. Check your email and password."
    if res is None or res.session is None or res.user is None:
        return False, "Sign-in failed. Check your email and password."

    _store_session(res.session, res.user)

    profile = _load_profile(client, res.user.id)
    if not profile:
        _forget_local()
        return False, ("Your account exists but has no profile yet. "
                       "Ask an administrator to create your camp profile.")
    st.session_state[_K_ROLE] = profile.get("role") or "camp_staff"
    st.session_state[_K_CAMP] = profile.get("camp_id") or None
    st.session_state[_K_CAMP_NAME] = _load_camp_name(client, st.session_state[_K_CAMP])
    return True, ""


def _forget_local() -> None:
    for key in (_K_ACCESS, _K_REFRESH, _K_EXPIRES, _K_USER_ID, _K_EMAIL,
                _K_ROLE, _K_CAMP, _K_CAMP_NAME):
        st.session_state.pop(key, None)
    clear_auth_context()


def sign_out() -> None:
    """End the Supabase session and clear all local auth state."""
    try:
        client = get_client()
        client.auth.sign_out()
    except Exception:
        pass
    _forget_local()


def ensure_auth() -> Optional[Dict[str, Any]]:
    """
    Validate/refresh the stored session, stamp the DB auth context so that
    RLS applies, and return the current user info (None when signed out).
    """
    if not auth_required():
        return None

    access = st.session_state.get(_K_ACCESS)
    user_id = st.session_state.get(_K_USER_ID)
    if not access or not user_id:
        return None

    try:
        client = get_client()
    except Exception:
        _forget_local()
        return None

    expires = int(st.session_state.get(_K_EXPIRES) or 0)
    if expires and time.time() > expires - 60:
        refresh = st.session_state.get(_K_REFRESH)
        try:
            res = client.auth.refresh_session(refresh) if refresh else None
            if res is None or res.session is None:
                raise RuntimeError("refresh failed")
            _store_session(res.session, res.user)
            access = res.session.access_token
        except Exception:
            # Refresh token invalid/expired -> fail closed to the login page
            _forget_local()
            return None
    else:
        try:
            client.auth.set_session(access, st.session_state.get(_K_REFRESH))
        except Exception:
            pass

    role = st.session_state.get(_K_ROLE) or "camp_staff"
    camp_id = st.session_state.get(_K_CAMP)

    set_auth_context(
        user_id=user_id,
        camp_id=camp_id,
        role=role,
        access_token=access,
    )

    return {
        "user_id": user_id,
        "email": st.session_state.get(_K_EMAIL),
        "role": role,
        "camp_id": camp_id or (None if role == "admin" else DEFAULT_CAMP_ID),
        "camp_name": st.session_state.get(_K_CAMP_NAME),
    }


def render_login_page() -> Dict[str, Any]:
    """Render the login form. Returns the user info dict after sign-in."""
    ok, err = supabase_configured()
    st.title("🔐 Staff Sign In")
    st.caption("Rural Healthcare Multilingual Feedback Agent — camp access is "
               "authorized per account and enforced by the database.")
    if not ok:
        st.error(err)
        st.info("Configure `.streamlit/secrets.toml` (SUPABASE_URL, "
                "SUPABASE_ANON_KEY) or set the environment variables.")
        return {}

    with st.form("supabase_login", clear_on_submit=False):
        email = st.text_input("Email", autocomplete="email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In", type="primary")
    if submitted:
        success, message = sign_in(email.strip(), password)
        if success:
            st.rerun()
        else:
            st.error(message)
    st.caption("Passwords are managed by Supabase Auth. They are never stored "
               "in this application or in GitHub.")
    return {}
