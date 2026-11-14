"""
Repeatable, NON-DESTRUCTIVE SQLite -> Supabase PostgreSQL migration.

Properties
----------
* The SQLite database is opened READ-ONLY and is never modified or deleted.
* Existing session/answer IDs are preserved (bigint identity columns accept
  explicit IDs; sequences are re-synced afterwards).
* Original transcripts, English translations, translation statuses/engines,
  languages, ratings and timestamps are copied verbatim.
* Idempotent: re-running never creates duplicates
  (`INSERT ... ON CONFLICT DO NOTHING`).
* Validates row counts, foreign keys, answer uniqueness and field-by-field
  transcript/translation equality, then writes a migration report.
* Requires an ADMINISTRATOR database connection (service side only). The
  Streamlit application never uses this mode.

Usage
-----
  # Dry run (no writes at all)
  python scripts/migrate_sqlite_to_supabase.py --dry-run

  # Real run (review the report afterwards)
  SUPABASE_DB_URL="postgresql://...session-pooler..." \
  SUPABASE_DB_ADMIN_MODE=1 \
  python scripts/migrate_sqlite_to_supabase.py

Optional arguments:
  --sqlite-path PATH      (default: data/healthcare_feedback.db)
  --camp-id UUID          target camp for imported sessions
                          (default: seeded "Default Camp")
  --report PATH           report output (default: migration_report.json)
"""
import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load repository .env (SUPABASE_DB_URL etc.) without overriding any variable
# already set in the shell environment.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

from database.context import DEFAULT_CAMP_ID  # noqa: E402

SESSION_COLUMNS = [
    "id", "patient_code", "patient_name", "village", "language",
    "consent_given", "status", "created_at", "completed_at", "camp_id",
]
ANSWER_COLUMNS = [
    "id", "session_id", "question_number", "question_text", "transcript",
    "response_type", "rating", "english_translation", "translation_status",
    "translation_engine", "source_language", "created_at",
]


def read_sqlite(path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Read sessions and answers from SQLite in READ-ONLY mode."""
    if not Path(path).exists():
        raise SystemExit(f"SQLite database not found: {path}")
    uri = f"file:{Path(path).resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        existing = {r[1] for r in conn.execute("PRAGMA table_info(feedback_sessions)")}
        sess_cols = [c for c in SESSION_COLUMNS if c in existing]
        cur = conn.execute(
            f"SELECT {', '.join(sess_cols)} FROM feedback_sessions ORDER BY id")
        sessions = [dict(r) for r in cur.fetchall()]

        ans_existing = {r[1] for r in conn.execute("PRAGMA table_info(feedback_answers)")}
        ans_cols = [c for c in ANSWER_COLUMNS if c in ans_existing]
        cur = conn.execute(
            f"SELECT {', '.join(ans_cols)} FROM feedback_answers ORDER BY id")
        answers = [dict(r) for r in cur.fetchall()]
        return sessions, answers
    finally:
        conn.close()


def connect_target():
    """Administrator connection to Supabase PostgreSQL (service side only)."""
    if not os.getenv("SUPABASE_DB_URL", "").strip():
        raise SystemExit(
            "SUPABASE_DB_URL is not set. Copy the Session-pooler connection "
            "string from the Supabase dashboard (Connect -> Session pooler).")
    from database.pg import connect

    conn = connect(admin=True)
    with conn.cursor() as cur:
        cur.execute("set time zone 'UTC'")  # SQLite CURRENT_TIMESTAMP is UTC
    conn.commit()
    return conn


def _existing_camp_ids(conn) -> set:
    with conn.cursor() as cur:
        cur.execute("select id::text from public.camps")
        return {r[0] for r in cur.fetchall()}


def import_rows(
    conn,
    sessions: List[Dict[str, Any]],
    answers: List[Dict[str, Any]],
    camp_id: str,
    dry_run: bool,
) -> Dict[str, Any]:
    known_camps = _existing_camp_ids(conn)
    stats = {
        "sessions_source": len(sessions),
        "answers_source": len(answers),
        "sessions_inserted": 0,
        "sessions_skipped_existing": 0,
        "answers_inserted": 0,
        "answers_skipped_existing": 0,
        "camp_fallbacks": 0,
        "dry_run": dry_run,
    }

    if dry_run:
        stats["sessions_inserted"] = 0
        stats["answers_inserted"] = 0
        stats["note"] = "dry-run: no rows written"
        return stats

    with conn.cursor() as cur:
        for s in sessions:
            sqlite_camp = s.get("camp_id")
            target_camp = sqlite_camp if sqlite_camp in known_camps else camp_id
            if target_camp != sqlite_camp:
                stats["camp_fallbacks"] += 1
            cur.execute(
                """
                insert into public.feedback_sessions
                    (id, camp_id, patient_code, patient_name, village, language,
                     consent_given, status, created_at, completed_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s,
                        coalesce(%s::timestamptz, current_timestamp),
                        %s::timestamptz)
                on conflict do nothing
                """,
                (
                    s["id"], target_camp, s["patient_code"],
                    s.get("patient_name"), s.get("village"), s["language"],
                    bool(s.get("consent_given", 1)), s.get("status", "in_progress"),
                    s.get("created_at"), s.get("completed_at"),
                ),
            )
            stats["sessions_inserted" if cur.rowcount else "sessions_skipped_existing"] += 1

        for a in answers:
            cur.execute(
                """
                insert into public.feedback_answers
                    (id, session_id, question_number, question_text, transcript,
                     response_type, rating, english_translation, translation_status,
                     translation_engine, source_language, created_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        coalesce(%s::timestamptz, current_timestamp))
                on conflict do nothing
                """,
                (
                    a["id"], a["session_id"], a["question_number"],
                    a["question_text"], a["transcript"], a["response_type"],
                    a.get("rating"), a.get("english_translation"),
                    a.get("translation_status") or "pending",
                    a.get("translation_engine"), a.get("source_language"),
                    a.get("created_at"),
                ),
            )
            stats["answers_inserted" if cur.rowcount else "answers_skipped_existing"] += 1

        # Move identity sequences past the imported explicit IDs so future
        # application inserts cannot collide.
        cur.execute("select public.resync_identity_sequences()")
        conn.commit()

    return stats


def validate(
    conn,
    sessions: List[Dict[str, Any]],
    answers: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Field-by-field validation of the imported data (read-only)."""
    checks: Dict[str, Any] = {"passed": True, "failures": []}

    def fail(name: str, detail: Any) -> None:
        checks["passed"] = False
        checks["failures"].append({name: detail})

    with conn.cursor() as cur:
        cur.execute("select count(*) from public.feedback_sessions")
        pg_sessions = cur.fetchone()[0]
        cur.execute("select count(*) from public.feedback_answers")
        pg_answers = cur.fetchone()[0]
        checks["counts"] = {
            "sqlite_sessions": len(sessions),
            "postgres_sessions": pg_sessions,
            "sqlite_answers": len(answers),
            "postgres_answers": pg_answers,
        }
        if pg_sessions < len(sessions):
            fail("session_count", "PostgreSQL has fewer sessions than SQLite")
        if pg_answers < len(answers):
            fail("answer_count", "PostgreSQL has fewer answers than SQLite")

        # Foreign key integrity
        cur.execute(
            """
            select count(*) from public.feedback_answers a
            left join public.feedback_sessions s on s.id = a.session_id
            where s.id is null
            """)
        orphans = cur.fetchone()[0]
        checks["orphan_answers"] = orphans
        if orphans:
            fail("foreign_keys", f"{orphans} answers reference missing sessions")

        # Answer uniqueness
        cur.execute(
            """
            select count(*) from (
                select session_id, question_number
                from public.feedback_answers
                group by session_id, question_number
                having count(*) > 1
            ) d
            """)
        duplicates = cur.fetchone()[0]
        checks["duplicate_session_question_pairs"] = duplicates
        if duplicates:
            fail("answer_uniqueness", f"{duplicates} duplicated (session, question) pairs")

        # Field-by-field content comparison for every source row
        cur.execute(
            """
            select id, session_id, question_number, transcript,
                   coalesce(english_translation, '') as english_translation,
                   translation_status, coalesce(translation_engine, '') as engine,
                   coalesce(source_language, '') as source_language
            from public.feedback_answers
            """
        )
        pg_rows = {r[0]: r for r in cur.fetchall()}
        transcript_mismatch, translation_mismatch, missing = [], [], []
        for a in answers:
            row = pg_rows.get(a["id"])
            if row is None:
                missing.append(a["id"])
                continue
            if (row[3] or "") != (a.get("transcript") or ""):
                transcript_mismatch.append(a["id"])
            if (row[4] or "") != (a.get("english_translation") or ""):
                translation_mismatch.append(a["id"])
            if (row[5] or "pending") != (a.get("translation_status") or "pending"):
                translation_mismatch.append(a["id"])
        checks["answers_missing_after_import"] = missing
        checks["transcript_mismatches"] = transcript_mismatch
        checks["translation_mismatches"] = translation_mismatch
        if missing:
            fail("missing_answers", f"{len(missing)} answers not found after import")
        if transcript_mismatch:
            fail("transcript_preservation",
                 f"{len(transcript_mismatch)} original transcripts differ")
        if translation_mismatch:
            fail("translation_preservation",
                 f"{len(translation_mismatch)} English translations/statuses differ")

        # Session ID preservation
        src_ids = {s["id"] for s in sessions}
        cur.execute("select id from public.feedback_sessions")
        pg_ids = {r[0] for r in cur.fetchall()}
        missing_sessions = sorted(src_ids - pg_ids)
        checks["sessions_missing_after_import"] = missing_sessions
        if missing_sessions:
            fail("session_ids", f"{len(missing_sessions)} session IDs missing")

        # Sequences must be ahead of max(id).
        # NOTE: pg_sequences.last_value is NULL when is_called = false (the
        # state resync_identity_sequences() leaves behind), so read the raw
        # sequence relation instead and compute the next value that nextval()
        # would hand out.
        def _next_value(seq_name: str):
            cur.execute(f"select last_value, is_called from public.{seq_name}")
            row = cur.fetchone()
            if row is None:
                return None
            last, is_called = row
            return int(last) + 1 if is_called else int(last)

        seq_s = _next_value("feedback_sessions_id_seq")
        seq_a = _next_value("feedback_answers_id_seq")
        cur.execute("select coalesce(max(id), 0) from public.feedback_sessions")
        max_s = cur.fetchone()[0]
        cur.execute("select coalesce(max(id), 0) from public.feedback_answers")
        max_a = cur.fetchone()[0]
        checks["sequence_positions"] = {
            "sessions_next_value": seq_s,
            "sessions_max_id": max_s,
            "answers_next_value": seq_a,
            "answers_max_id": max_a,
        }
        if seq_s is None or seq_a is None or seq_s <= max_s or seq_a <= max_a:
            fail("sequences", "identity sequence not ahead of max(id)")

    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite-path",
                        default=os.getenv("DATABASE_PATH", "data/healthcare_feedback.db"))
    parser.add_argument("--camp-id", default=DEFAULT_CAMP_ID,
                        help="target camp UUID for imported sessions")
    parser.add_argument("--report", default="migration_report.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="read and plan only; writes nothing")
    args = parser.parse_args()

    started = time.time()
    sessions, answers = read_sqlite(args.sqlite_path)

    report: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sqlite_path": str(Path(args.sqlite_path).resolve()),
        "sqlite_mode": "read-only",
        "dry_run": args.dry_run,
        "target_camp_id": args.camp_id,
        "target": "(SUPABASE_DB_URL host only, credentials never recorded)",
    }

    conn = connect_target()
    try:
        with conn.cursor() as cur:
            cur.execute("select current_setting('host', true)")
            host = cur.fetchone()[0]
            report["target_host"] = host
            cur.execute("select version()")
            report["postgres_version"] = cur.fetchone()[0]

        report["import"] = import_rows(
            conn, sessions, answers, args.camp_id, args.dry_run)
        if args.dry_run:
            report["validation"] = {
                "passed": True,
                "status": "skipped_dry_run",
                "note": "No rows were written, so there is nothing to validate.",
                "source_counts": {
                    "sessions": len(sessions),
                    "answers": len(answers),
                },
            }
        else:
            report["validation"] = validate(conn, sessions, answers)
    finally:
        conn.close()

    report["duration_seconds"] = round(time.time() - started, 2)
    report["result"] = "VALIDATION_PASSED" if report["validation"]["passed"] \
        else "VALIDATION_FAILED"

    Path(args.report).write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nReport written to: {args.report}")
    if not report["validation"]["passed"]:
        print("VALIDATION FAILED — review the failures before proceeding.")
        return 1
    print("Validation passed. SQLite data left untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
