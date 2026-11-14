"""
SQLite regression tests: the pre-existing local backend must keep working
exactly as before (no breaking changes from the Phase 1 changes).

All writes go to a TEMPORARY database file — the real
data/healthcare_feedback.db is never opened for writing.
"""
import pandas as pd

from database.context import DEFAULT_CAMP_ID as DEFAULT_CAMP_ID_FALLBACK


def test_sqlite_remains_default_when_supabase_url_is_configured(monkeypatch):
    import database.db as db

    monkeypatch.setattr(db, "_BACKEND", "")
    monkeypatch.delenv("DB_BACKEND", raising=False)
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://configured.example/database")

    assert db.get_backend() == "sqlite"


def test_sqlite_backend_unchanged(sqlite_env):
    from database.db import get_backend, get_connection, init_db
    from database.repository import (
        complete_feedback_session,
        count_feedback_records,
        create_feedback_session,
        get_all_feedback_records,
        get_all_sessions,
        get_analytics_summary,
        get_feedback_by_session,
        save_feedback_answer,
        update_answer_translation,
    )

    assert get_backend() == "sqlite"

    # Idempotent initialisation (run twice, as app.py + api.py both call it)
    init_db()
    init_db()

    # Schema gained the additive camp_id column with a default
    conn = get_connection()
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(feedback_sessions)")]
        assert "camp_id" in cols
    finally:
        conn.close()

    # Hindi session with the original test transcripts
    sid = create_feedback_session("hi", patient_code="PAT-LOCAL-001")
    answers = [
        (1, "मेरा नाम रामेश्वर पटेल है, रामपुर गाँव।", "open_response", None),
        (3, "स्वास्थ्य सहायक ने बहुत अच्छे से देखा।", "rating", 5),
    ]
    for q_num, transcript, resp_type, rating in answers:
        save_feedback_answer(
            session_id=sid, question_number=q_num,
            question_text=f"Q{q_num}", transcript=transcript,
            response_type=resp_type, rating=rating, source_language="hi")

    # Duplicate prevention still holds
    save_feedback_answer(
        session_id=sid, question_number=3, question_text="Q3",
        transcript="स्वास्थ्य सहायक ने बहुत अच्छे से देखा।",
        response_type="rating", rating=5, source_language="hi")

    data = get_feedback_by_session(sid)
    assert len(data["answers"]) == 2
    assert data["patient_name"] == answers[0][1]
    assert data["camp_id"] == DEFAULT_CAMP_ID_FALLBACK

    update_answer_translation(
        session_id=sid, question_number=3,
        english_translation="The health assistant examined me very well.",
        translation_status="translated", translation_engine="nllb-200-distilled-600M-ctranslate2-int8")
    ans = [a for a in get_feedback_by_session(sid)["answers"] if a["question_number"] == 3][0]
    assert ans["transcript"] == "स्वास्थ्य सहायक ने बहुत अच्छे से देखा।"
    assert ans["translation_status"] == "translated"

    assert complete_feedback_session(sid) is True
    assert get_feedback_by_session(sid)["status"] == "completed"

    # Reporting helpers + pagination + filters
    records = get_all_feedback_records()
    assert any(r["session_id"] == sid for r in records)
    assert count_feedback_records() >= 2
    page = get_all_feedback_records(limit=1, offset=0)
    assert len(page) == 1
    assert count_feedback_records(language="hi") >= 1
    assert count_feedback_records(search="PAT-LOCAL-001") == 2  # 2 answer rows

    summary = get_analytics_summary()
    assert summary["total_sessions"] >= 1
    assert summary["completed_sessions"] >= 1

    # CSV export shape used by the admin dashboard
    df = pd.DataFrame(records)
    df["original_transcript"] = df["transcript"]
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    assert b"original_transcript" in csv_bytes and b"english_translation" in csv_bytes

    assert any(s["id"] == sid for s in get_all_sessions(limit=50))
