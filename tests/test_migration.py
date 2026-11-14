"""
SQLite -> Supabase PostgreSQL migration tests (LOCAL PostgreSQL only).

- Uses a TEMPORARY synthetic SQLite database (never the real data file).
- Verifies: ID preservation, verbatim transcripts/translations, foreign keys,
  answer uniqueness, sequence resynchronisation, idempotent re-runs, dry-run
  safety, and that SQLite is never modified.
- Also performs a READ-ONLY dry-run against the real SQLite database when it
  exists (aggregate counts only; no patient content is printed or copied).
"""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import PG_AVAILABLE, requires_pg

pytestmark = requires_pg

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "migrate_sqlite_to_supabase.py"

SYNTH_SESSIONS = [
    # (id, patient_code, language, status, created_at, patient_name, village)
    (5001, "PAT-SYN-001", "hi", "completed", "2026-01-05 10:00:00",
     "सुनीता देवी", "रामपुर"),
    (5002, "PAT-SYN-002", "te", "completed", "2026-01-06 11:30:00",
     "రామ య్య", "పాలెం"),
    (5003, "PAT-SYN-003", "hi", "in_progress", "2026-01-07 09:15:00", None, None),
]

SYNTH_ANSWERS = [
    # (id, session_id, q, question_text, transcript, response_type, rating,
    #  english_translation, translation_status, translation_engine, source_language, created_at)
    (9001, 5001, 1, "Name?", "मेरा नाम सुनीता देवी है।", "open_response", None,
     "My name is Sunita Devi.", "translated", "nllb-200-distilled-600M-ctranslate2-int8",
     "hi", "2026-01-05 10:00:05"),
    (9002, 5001, 3, "Rating?", "सेवा अच्छी थी", "rating", 4,
     "The service was good.", "translated", "nllb-200-distilled-600M-ctranslate2-int8",
     "hi", "2026-01-05 10:01:00"),
    (9003, 5001, 5, "Suggestion?", "दवाइयाँ समय पर मिलें।", "open_response", None,
     "", "failed", "nllb-200-distilled-600M-ctranslate2-int8", "hi",
     "2026-01-05 10:02:00"),
    (9004, 5002, 1, "Name?", "నా పేరు రామ య్య", "open_response", None,
     "", "pending", None, "te", "2026-01-06 11:30:05"),
    (9005, 5002, 4, "Understood?", "అవును, స్పష్టంగా చెప్పారు.", "yes", None,
     "Yes, they explained clearly.", "translated", "nllb-200-distilled-600M-ctranslate2-int8",
     "te", "2026-01-06 11:31:00"),
    (9006, 5003, 1, "Name?", "राजेश कुमार", "open_response", None,
     None, "pending", None, "hi", "2026-01-07 09:15:03"),
]


def _build_sqlite(path: Path) -> None:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE feedback_sessions (
            id INTEGER PRIMARY KEY,
            patient_code TEXT NOT NULL,
            patient_name TEXT,
            village TEXT,
            language TEXT NOT NULL,
            consent_given BOOLEAN NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'in_progress',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            camp_id TEXT DEFAULT '00000000-0000-0000-0000-000000000001'
        )""")
    cur.execute("""
        CREATE TABLE feedback_answers (
            id INTEGER PRIMARY KEY,
            session_id INTEGER NOT NULL,
            question_number INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            transcript TEXT NOT NULL,
            response_type TEXT NOT NULL,
            rating INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            english_translation TEXT,
            translation_status TEXT DEFAULT 'pending',
            translation_engine TEXT,
            source_language TEXT,
            FOREIGN KEY (session_id) REFERENCES feedback_sessions(id) ON DELETE CASCADE,
            UNIQUE(session_id, question_number)
        )""")
    for s in SYNTH_SESSIONS:
        cur.execute(
            "INSERT INTO feedback_sessions "
            "(id, patient_code, language, status, created_at, patient_name, village, consent_given) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 1)", s)
    cur.execute("UPDATE feedback_sessions SET completed_at = created_at WHERE status = 'completed'")
    for a in SYNTH_ANSWERS:
        cur.execute(
            "INSERT INTO feedback_answers "
            "(id, session_id, question_number, question_text, transcript, response_type, "
            " rating, english_translation, translation_status, translation_engine, "
            " source_language, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", a)
    conn.commit()
    conn.close()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(args):
    env = dict(os.environ)
    env["DB_BACKEND"] = "postgres"
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(REPO), env=env, capture_output=True, text=True, encoding="utf-8")


def _pg_admin():
    from database.pg import connect
    return connect(admin=True)


@pytest.fixture()
def synthetic_sqlite(tmp_path):
    path = tmp_path / "synthetic.db"
    _build_sqlite(path)
    return path


def _truncate_feedback():
    conn = _pg_admin()
    try:
        cur = conn.cursor()
        cur.execute("truncate table public.feedback_sessions, public.feedback_answers "
                    "restart identity cascade")
        conn.commit()
    finally:
        conn.close()


def test_migration_validates_and_is_idempotent(synthetic_sqlite, tmp_path):
    _truncate_feedback()
    sqlite_hash_before = _sha256(synthetic_sqlite)
    report_path = tmp_path / "report1.json"

    # --- Run 1: import -----------------------------------------------------
    res = _run(["--sqlite-path", str(synthetic_sqlite), "--report", str(report_path)])
    assert res.returncode == 0, f"migration failed:\n{res.stdout}\n{res.stderr}"
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["result"] == "VALIDATION_PASSED", report["validation"]
    assert report["validation"]["passed"] is True
    assert report["import"]["sessions_inserted"] == len(SYNTH_SESSIONS)
    assert report["import"]["answers_inserted"] == len(SYNTH_ANSWERS)
    assert report["validation"]["counts"] == {
        "sqlite_sessions": len(SYNTH_SESSIONS),
        "postgres_sessions": len(SYNTH_SESSIONS),
        "sqlite_answers": len(SYNTH_ANSWERS),
        "postgres_answers": len(SYNTH_ANSWERS),
    }
    assert report["validation"]["orphan_answers"] == 0
    assert report["validation"]["duplicate_session_question_pairs"] == 0
    assert report["validation"]["transcript_mismatches"] == []
    assert report["validation"]["translation_mismatches"] == []
    assert report["validation"]["sessions_missing_after_import"] == []
    assert report["validation"]["answers_missing_after_import"] == []

    # IDs, transcripts and translations preserved exactly (direct check)
    conn = _pg_admin()
    try:
        cur = conn.cursor()
        cur.execute("select id, transcript, english_translation, translation_status "
                    "from public.feedback_answers order by id")
        rows = {r[0]: r for r in cur.fetchall()}
        assert sorted(rows) == [a[0] for a in SYNTH_ANSWERS]
        for a in SYNTH_ANSWERS:
            row = rows[a[0]]
            assert row[1] == a[4], "original transcript altered"
            assert (row[2] or "") == (a[7] or "")
            assert row[3] == a[8]
        cur.execute("select id, camp_id::text from public.feedback_sessions order by id")
        sess = cur.fetchall()
        assert [r[0] for r in sess] == [s[0] for s in SYNTH_SESSIONS]
        assert all(r[1] for r in sess), "session without camp"
        # sequences moved past max(id) (raw seq: is_called=false -> next = last)
        cur.execute("select last_value, is_called from public.feedback_answers_id_seq")
        last, is_called = cur.fetchone()
        next_val = int(last) + 1 if is_called else int(last)
        assert next_val > max(a[0] for a in SYNTH_ANSWERS)
    finally:
        conn.close()

    # SQLite untouched
    assert _sha256(synthetic_sqlite) == sqlite_hash_before

    # --- Run 2: repeatable, no duplicates ---------------------------------
    report_path2 = tmp_path / "report2.json"
    res2 = _run(["--sqlite-path", str(synthetic_sqlite), "--report", str(report_path2)])
    assert res2.returncode == 0, f"re-run failed:\n{res2.stdout}\n{res2.stderr}"
    report2 = json.loads(report_path2.read_text(encoding="utf-8"))
    assert report2["result"] == "VALIDATION_PASSED"
    assert report2["import"]["sessions_inserted"] == 0
    assert report2["import"]["sessions_skipped_existing"] == len(SYNTH_SESSIONS)
    assert report2["import"]["answers_inserted"] == 0
    assert report2["import"]["answers_skipped_existing"] == len(SYNTH_ANSWERS)
    assert report2["validation"]["counts"]["postgres_sessions"] == len(SYNTH_SESSIONS)
    assert report2["validation"]["counts"]["postgres_answers"] == len(SYNTH_ANSWERS)
    assert _sha256(synthetic_sqlite) == sqlite_hash_before

    # --- Dry run: writes nothing ------------------------------------------
    report_path3 = tmp_path / "report3.json"
    res3 = _run(["--sqlite-path", str(synthetic_sqlite), "--report", str(report_path3),
                 "--dry-run"])
    assert res3.returncode == 0, res3.stderr
    report3 = json.loads(report_path3.read_text(encoding="utf-8"))
    assert report3["dry_run"] is True
    assert report3["validation"]["status"] == "skipped_dry_run"
    assert report3["import"]["sessions_inserted"] == 0
    assert _sha256(synthetic_sqlite) == sqlite_hash_before

    # Report must never contain credentials
    for text in (report_path, report_path2, report_path3):
        content = text.read_text(encoding="utf-8").lower()
        assert "password=" not in content
        assert "postgres:postgres" not in content


def test_migration_dry_run_reads_real_sqlite_without_copying(tmp_path):
    """Read-only dry run against the real database: counts only, no writes."""
    real_db = REPO / "data" / "healthcare_feedback.db"
    if not real_db.exists():
        pytest.skip("no local SQLite database present")
    hash_before = _sha256(real_db)
    report_path = tmp_path / "real_dry_run.json"
    res = _run(["--sqlite-path", str(real_db), "--report", str(report_path),
                "--dry-run"])
    assert res.returncode == 0, f"dry run failed:\n{res.stdout}\n{res.stderr}"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["dry_run"] is True
    assert report["sqlite_mode"] == "read-only"
    assert report["import"]["sessions_source"] >= 0
    assert report["import"]["answers_source"] >= 0
    # Only aggregate counts are reported — no patient content
    assert "transcript" not in report_path.read_text(encoding="utf-8").lower()
    # The real database file is byte-identical after the dry run
    assert _sha256(real_db) == hash_before
