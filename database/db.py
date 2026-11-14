"""
Database initialization and connection management.

Two backends are supported (selected once per process):

  sqlite    (default)  -> existing local file database, unchanged behaviour
  postgres  (supabase) -> set DB_BACKEND=postgres (or SUPABASE_DB_URL)

In PostgreSQL mode the schema is owned by the Supabase SQL migrations in
`supabase/migrations/`; `init_db()` becomes a no-op so nothing local is
assumed. No credentials are stored in code.
"""
import os
import sqlite3
from pathlib import Path

# Load environment variables safely with built-in fallback if python-dotenv is missing
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    for candidate in [Path(".env"), Path(__file__).resolve().parent.parent / ".env"]:
        if candidate.is_file():
            try:
                for line in candidate.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip('"').strip("'")
                        if k not in os.environ:
                            os.environ[k] = v
            except Exception:
                pass
            break

DEFAULT_DB_PATH = os.getenv("DATABASE_PATH", "data/healthcare_feedback.db")

_BACKEND = os.getenv("DB_BACKEND", "").strip().lower()


def get_backend() -> str:
    """Return 'sqlite' or 'postgres' for this process."""
    global _BACKEND
    if not _BACKEND:
        _BACKEND = "postgres" if os.getenv("SUPABASE_DB_URL", "").strip() else "sqlite"
    if _BACKEND in ("postgres", "postgresql", "supabase"):
        return "postgres"
    return "sqlite"


def get_db_path() -> str:
    path_str = os.getenv("DATABASE_PATH", DEFAULT_DB_PATH)
    path = Path(path_str)
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)

def get_connection():
    """
    Open a database connection for the active backend.
    Returns a sqlite3.Connection (sqlite) or a compatible PgConnection
    (postgres). Both expose cursor()/commit()/rollback()/close() with
    sqlite3-style rows.
    """
    if get_backend() == "postgres":
        from .pg import connect
        return connect()

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Create database tables if they do not exist and apply schema migrations."""
    if get_backend() == "postgres":
        # Schema is managed by supabase/migrations/*.sql (Supabase SQL Editor).
        # Deliberately creates nothing locally: no SQLite dependency in cloud mode.
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_code TEXT NOT NULL,
                patient_name TEXT,
                village TEXT,
                language TEXT NOT NULL,
                consent_given BOOLEAN NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'in_progress',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            );
        """)

        # Ensure migration columns for patient_name and village exist if table pre-existed
        cursor.execute("PRAGMA table_info(feedback_sessions);")
        columns = [col[1] for col in cursor.fetchall()]
        if "patient_name" not in columns:
            cursor.execute("ALTER TABLE feedback_sessions ADD COLUMN patient_name TEXT;")
        if "village" not in columns:
            cursor.execute("ALTER TABLE feedback_sessions ADD COLUMN village TEXT;")
        # Additive camp scoping column (multi-camp support); existing rows are
        # assigned the default camp. Non-destructive.
        if "camp_id" not in columns:
            from .context import DEFAULT_CAMP_ID
            cursor.execute(
                f"ALTER TABLE feedback_sessions ADD COLUMN camp_id TEXT DEFAULT '{DEFAULT_CAMP_ID}';"
            )

        # Answers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                question_number INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                transcript TEXT NOT NULL,
                response_type TEXT NOT NULL,
                rating INTEGER,
                english_translation TEXT,
                translation_status TEXT NOT NULL DEFAULT 'pending',
                translation_engine TEXT,
                source_language TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES feedback_sessions(id) ON DELETE CASCADE,
                UNIQUE(session_id, question_number)
            );
        """)

        # Migration: ensure translation columns exist in pre-existing tables
        cursor.execute("PRAGMA table_info(feedback_answers);")
        ans_cols = [col[1] for col in cursor.fetchall()]
        if "english_translation" not in ans_cols:
            cursor.execute("ALTER TABLE feedback_answers ADD COLUMN english_translation TEXT;")
        if "translation_status" not in ans_cols:
            cursor.execute("ALTER TABLE feedback_answers ADD COLUMN translation_status TEXT DEFAULT 'pending';")
        if "translation_engine" not in ans_cols:
            cursor.execute("ALTER TABLE feedback_answers ADD COLUMN translation_engine TEXT;")
        if "source_language" not in ans_cols:
            cursor.execute("ALTER TABLE feedback_answers ADD COLUMN source_language TEXT;")

        # Safe backfill for pre-existing answers
        cursor.execute("""
            UPDATE feedback_answers
            SET source_language = (
                SELECT language FROM feedback_sessions WHERE feedback_sessions.id = feedback_answers.session_id
            )
            WHERE source_language IS NULL;
        """)
        cursor.execute("""
            UPDATE feedback_answers
            SET english_translation = transcript,
                translation_status = 'not_required',
                translation_engine = 'identity_en'
            WHERE source_language = 'en' AND (translation_status IS NULL OR translation_status = 'pending');
        """)
        cursor.execute("""
            UPDATE feedback_answers
            SET translation_status = 'pending'
            WHERE translation_status IS NULL;
        """)

        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at", get_db_path())
