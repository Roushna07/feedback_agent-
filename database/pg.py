"""
PostgreSQL (Supabase) connection backend.

Provides a sqlite3-compatible facade (connection/cursor/Row) so the existing
repository code runs unchanged against Supabase PostgreSQL:

  * `?` placeholders are converted to psycopg's `%s`
  * `cursor.lastrowid` is emulated with `RETURNING id` for INSERTs
  * rows support both integer indexing (row[0]) and key access (row["id"])

Security:
  * When an authentication context exists (signed-in user), the connection
    runs `SET ROLE authenticated` and sets `request.jwt.claims`, so Supabase
    Row Level Security is enforced on every statement.
  * Without a context the connection is refused, unless the explicit
    `SUPABASE_DB_ADMIN_MODE=1` escape hatch is set (migration/seed scripts
    only, never used by the Streamlit application).
"""
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import psycopg
from psycopg import sql as _pg_sql  # noqa: F401  (kept for future use)

from .context import jwt_claims_json

_PLACEHOLDER = "%s"

# Matches string literals / quoted identifiers so we never rewrite inside them
_TOKEN_RE = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|--[^\n]*|/\*.*?\*/",
                       re.DOTALL)

_INSERT_RE = re.compile(r"^\s*insert\b", re.IGNORECASE)
_RETURNING_RE = re.compile(r"\breturning\b", re.IGNORECASE)


class Row:
    """sqlite3.Row-compatible row (integer index + column name access)."""

    __slots__ = ("_keys", "_values")

    def __init__(self, keys: Sequence[str], values: Sequence[Any]):
        self._keys = list(keys)
        self._values = list(values)

    def keys(self) -> List[str]:
        return list(self._keys)

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, (int, slice)):
            return self._values[key]
        try:
            idx = self._keys.index(key)
        except ValueError:
            raise IndexError(f"No item with that key: {key!r}") from None
        return self._values[idx]

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Row):
            return self._keys == other._keys and self._values == other._values
        if isinstance(other, (list, tuple)):
            return tuple(self._values) == tuple(other)
        return NotImplemented

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Row {dict(zip(self._keys, self._values))!r}>"


def convert_query(query: str) -> Tuple[str, bool]:
    """
    Convert a SQLite-style query to psycopg style.

    Returns (converted_query, returns_id) where returns_id is True when we
    appended `RETURNING id` to capture lastrowid.
    """
    out: List[str] = []
    pos = 0
    for match in _TOKEN_RE.finditer(query):
        chunk = query[pos:match.start()]
        out.append(_convert_chunk(chunk))
        out.append(match.group(0))  # literal / comment copied verbatim
        pos = match.end()
    out.append(_convert_chunk(query[pos:]))
    converted = "".join(out)

    returns_id = False
    if _INSERT_RE.match(query) and not _RETURNING_RE.search(query):
        # Only our own tables expose `id`; appending RETURNING is safe for
        # INSERT ... VALUES / INSERT ... ON CONFLICT used by the repository.
        converted = f"{converted} RETURNING id"
        returns_id = True
    return converted, returns_id


def _convert_chunk(chunk: str) -> str:
    """Convert one non-literal chunk: `?` -> `%s`, literal `%` -> `%%`.
    Already-psycopg-style `%s` / `%%` sequences are passed through so callers
    may use either placeholder style."""
    result = []
    i = 0
    n = len(chunk)
    while i < n:
        ch = chunk[i]
        if ch == "?":
            result.append(_PLACEHOLDER)
            i += 1
        elif ch == "%":
            nxt = chunk[i + 1] if i + 1 < n else ""
            if nxt == "s":
                result.append(_PLACEHOLDER)
                i += 2
            elif nxt == "%":
                result.append("%%")
                i += 2
            else:
                result.append("%%")
                i += 1
        else:
            result.append(ch)
            i += 1
    return "".join(result)


class PgCursor:
    def __init__(self, conn: "PgConnection"):
        self._conn = conn
        self._cursor = conn._conn.cursor()
        self._returns_id = False
        self.lastrowid: Optional[int] = None

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    def execute(self, query: str, params: Optional[Sequence[Any]] = None):
        converted, returns_id = convert_query(query)
        self._returns_id = returns_id
        self.lastrowid = None
        if params is None:
            self._cursor.execute(converted)
        else:
            self._cursor.execute(converted, tuple(params))
        if returns_id:
            row = self._cursor.fetchone()
            if row is not None:
                self.lastrowid = row[0]
        return self

    def fetchone(self) -> Optional[Row]:
        row = self._cursor.fetchone()
        if row is None:
            return None
        return self._to_row(row)

    def fetchall(self) -> List[Row]:
        return [self._to_row(r) for r in self._cursor.fetchall()]

    def _to_row(self, values: Sequence[Any]) -> Row:
        desc = self._cursor.description
        keys = [d[0] for d in desc] if desc else []
        # SQLite returns uuid TEXT columns as str; mirror that so application
        # code can compare camp_id/user_id with plain strings.
        import uuid as _uuid
        norm = [
            str(v) if isinstance(v, _uuid.UUID) else v for v in values
        ]
        return Row(keys, norm)

    def close(self) -> None:
        self._cursor.close()

    def __enter__(self) -> "PgCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class PgConnection:
    """sqlite3.Connection-compatible wrapper."""

    def __init__(self, conn: psycopg.Connection, admin: bool = False):
        self._conn = conn
        self.admin = admin

    def cursor(self) -> PgCursor:
        return PgCursor(self)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        try:
            self._conn.commit()
        except Exception:
            try:
                self._conn.rollback()
            except Exception:
                pass
        self._conn.close()

    def __enter__(self) -> "PgConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.close()
        else:
            try:
                self._conn.rollback()
            finally:
                self._conn.close()


def _dsn_from_env() -> str:
    dsn = os.getenv("SUPABASE_DB_URL", "").strip()
    if dsn:
        return dsn
    host = os.getenv("SUPABASE_DB_HOST", "").strip()
    if host:
        return (
            "postgresql://{user}:{password}@{host}:{port}/{database}".format(
                user=os.getenv("SUPABASE_DB_USER", "postgres"),
                password=os.getenv("SUPABASE_DB_PASSWORD", ""),
                host=host,
                port=os.getenv("SUPABASE_DB_PORT", "5432"),
                database=os.getenv("SUPABASE_DB_NAME", "postgres"),
            )
        )
    raise RuntimeError(
        "PostgreSQL backend selected but no connection string found. "
        "Set SUPABASE_DB_URL (Supabase Dashboard -> Connect -> Session pooler)."
    )


def connect(admin: Optional[bool] = None) -> PgConnection:
    """
    Open a PostgreSQL connection applying RLS impersonation when a user is
    signed in. Raises (fail-closed) when neither a user nor an explicit
    admin connection is requested.

    admin=True is only for administrative scripts (migration/seed): it skips
    the user impersonation and therefore runs as the table owner, where RLS
    does not apply. The Streamlit application never calls it.
    """
    dsn = _dsn_from_env()
    sslmode = os.getenv("SUPABASE_DB_SSLMODE", "").strip()
    if sslmode and "sslmode=" not in dsn:
        sep = "&" if "?" in dsn else "?"
        dsn = f"{dsn}{sep}sslmode={sslmode}"

    connect_timeout = os.getenv("SUPABASE_DB_CONNECT_TIMEOUT", "10")

    try:
        conn = psycopg.connect(dsn, connect_timeout=int(connect_timeout))
    except psycopg.OperationalError as exc:
        raise RuntimeError(
            f"Could not reach PostgreSQL: {exc}. "
            "Check SUPABASE_DB_URL / network and retry; the SQLite database "
            "is untouched."
        ) from exc

    claims_json = jwt_claims_json()
    if admin is None:
        admin = os.getenv("SUPABASE_DB_ADMIN_MODE", "").strip() == "1"

    try:
        if claims_json:
            with conn.cursor() as cur:
                cur.execute(
                    "select set_config('request.jwt.claims', %s, false)",
                    (claims_json,),
                )
                cur.execute("set role authenticated")
            conn.commit()
        elif not admin:
            conn.close()
            raise RuntimeError(
                "Refusing to open an unauthenticated PostgreSQL connection. "
                "Sign in first, or call connect(admin=True) explicitly from "
                "an administrative script (never from the app)."
            )
        else:
            conn.commit()
    except psycopg.errors.InsufficientPrivilege as exc:
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        raise RuntimeError(
            "PostgreSQL refused role impersonation for Row Level Security "
            f"({exc}). Run once in the Supabase SQL Editor: "
            "`grant authenticated to postgres;` (see "
            "supabase/migrations/0003_rls_policies.sql)."
        ) from exc
    except psycopg.Error:
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        raise

    return PgConnection(conn, admin=(claims_json is None))
