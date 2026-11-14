"""
Per-process authentication context for database access.

The PostgreSQL backend uses the signed-in user's JWT so that Row Level
Security is enforced on every query. The Streamlit auth layer (or a test)
stamps the context here before any repository call; SQLite mode ignores it.

Thread-safe: uses a threading.local so concurrent sessions never share
credentials.
"""
import json
import threading
from typing import Any, Dict, Optional

_local = threading.local()

# Fixed identifier of the seeded "Default Camp" (see supabase/migrations/0001).
DEFAULT_CAMP_ID = "00000000-0000-0000-0000-000000000001"


def set_auth_context(
    user_id: Optional[str],
    camp_id: Optional[str] = None,
    role: Optional[str] = None,
    access_token: Optional[str] = None,
) -> None:
    """Store the current user's identity for RLS-scoped PostgreSQL access."""
    _local.ctx = {
        "user_id": user_id,
        "camp_id": camp_id,
        "role": role,
        "access_token": access_token,
    }


def clear_auth_context() -> None:
    """Drop the current user's identity (logout)."""
    _local.ctx = None


def get_auth_context() -> Dict[str, Any]:
    """Return the current context (empty dict when unauthenticated)."""
    return dict(getattr(_local, "ctx", None) or {})


def jwt_claims() -> Optional[Dict[str, Any]]:
    """
    Claims used for `request.jwt.claims` on a direct Postgres connection.
    Only `sub` is required by auth.uid(); role is enforced via SET ROLE.
    """
    ctx = get_auth_context()
    user_id = ctx.get("user_id")
    if not user_id:
        return None
    return {"sub": user_id, "role": "authenticated"}


def jwt_claims_json() -> Optional[str]:
    claims = jwt_claims()
    return json.dumps(claims) if claims else None
