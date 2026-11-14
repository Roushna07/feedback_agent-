"""
PostgreSQL (Supabase-compatible) backend tests.

Run against the LOCAL Docker PostgreSQL created by tests/start_local_pg.ps1.
Synthetic patient records only. Skipped automatically when that database is
not reachable — these tests never contact a real Supabase project.
"""
import csv
import io
import os

import pandas as pd
import pytest

from tests.conftest import ADMIN_ALL, CAMP_A, CAMP_B, STAFF_A, STAFF_B, requires_pg

pytestmark = requires_pg

HI_TRANSCRIPT = "मेरा नाम रामेश्वर पटेल है, रामपुर गाँव।"
TE_TRANSCRIPT = "నా పేరు కృష్ణారెడ్డి, మాది పాలెం గ్రామం."


def _clear_feedback(admin_conn):
    """Remove synthetic feedback rows (users/camps are kept)."""
    cur = admin_conn.cursor()
    cur.execute("truncate table public.feedback_sessions, public.feedback_answers "
                "restart identity cascade")
    admin_conn.commit()


# ---------------------------------------------------------------------------
# Connection behaviour
# ---------------------------------------------------------------------------
def test_connection_without_identity_fails_closed(monkeypatch):
    from database.context import clear_auth_context
    from database.pg import connect
    clear_auth_context()
    monkeypatch.delenv("SUPABASE_DB_ADMIN_MODE", raising=False)
    with pytest.raises(RuntimeError, match="unauthenticated"):
        connect(admin=False)


def test_connection_with_identity_succeeds(as_staff_a):
    from database.pg import connect
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("select current_user, auth.uid()")
        row = cur.fetchone()
        assert str(row[1]) == STAFF_A, "auth.uid() must resolve from JWT claims"
        assert row[0] == "authenticated", "connection must run as authenticated"
    finally:
        conn.close()


def test_disconnection_and_recovery(as_staff_a, monkeypatch):
    from database.pg import connect
    from database.repository import get_all_sessions

    good_url = os.environ["SUPABASE_DB_URL"]
    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:postgres@127.0.0.1:59999/postgres")
    with pytest.raises(RuntimeError, match="Could not reach PostgreSQL"):
        connect()
    with pytest.raises(RuntimeError, match="Could not reach PostgreSQL"):
        get_all_sessions(limit=1)   # repository surfaces the same clear error

    monkeypatch.setenv("SUPABASE_DB_URL", good_url)
    sessions = get_all_sessions(limit=1)
    assert isinstance(sessions, list)  # recovered on the next call


# ---------------------------------------------------------------------------
# Session + answer lifecycle
# ---------------------------------------------------------------------------
def test_session_answer_lifecycle(admin_conn, as_staff_a):
    from database.repository import (
        complete_feedback_session,
        create_feedback_session,
        get_feedback_by_session,
        save_feedback_answer,
    )
    _clear_feedback(admin_conn)

    sid = create_feedback_session(language="hi", patient_name=None, village=None)
    assert isinstance(sid, int) and sid >= 1

    save_feedback_answer(
        session_id=sid, question_number=1,
        question_text="What is your name?", transcript=HI_TRANSCRIPT,
        response_type="open_response", source_language="hi")
    save_feedback_answer(
        session_id=sid, question_number=3,
        question_text="How was the service?", transcript="सेवा बहुत अच्छी थी।",
        response_type="rating", rating=5, source_language="hi")

    data = get_feedback_by_session(sid)
    assert data["status"] == "in_progress"
    assert len(data["answers"]) == 2
    assert data["patient_name"] == HI_TRANSCRIPT  # Q1 side effect preserved
    assert data["camp_id"] == CAMP_A               # created under staff A's camp

    assert complete_feedback_session(sid) is True
    data = get_feedback_by_session(sid)
    assert data["status"] == "completed"
    assert data["completed_at"] is not None


def test_duplicate_answer_prevention(admin_conn, as_staff_a):
    from database.repository import create_feedback_session, get_feedback_by_session, save_feedback_answer
    _clear_feedback(admin_conn)

    sid = create_feedback_session(language="hi")
    for _ in range(3):
        save_feedback_answer(
            session_id=sid, question_number=2, question_text="Symptoms?",
            transcript=HI_TRANSCRIPT, response_type="open_response",
            source_language="hi")
    data = get_feedback_by_session(sid)
    assert len(data["answers"]) == 1, "duplicate (session, question) rows created"

    # Upsert overwrites the row instead of adding one
    save_feedback_answer(
        session_id=sid, question_number=2, question_text="Symptoms?",
        transcript="Updated transcript", response_type="open_response",
        source_language="hi")
    data = get_feedback_by_session(sid)
    assert len(data["answers"]) == 1
    assert data["answers"][0]["transcript"] == "Updated transcript"


def test_original_transcript_preserved_and_translation_persisted(admin_conn, as_staff_a):
    from database.repository import (
        create_feedback_session,
        get_feedback_by_session,
        save_feedback_answer,
        update_answer_translation,
    )
    _clear_feedback(admin_conn)

    sid = create_feedback_session(language="te")
    save_feedback_answer(
        session_id=sid, question_number=5, question_text="Suggestions?",
        transcript=TE_TRANSCRIPT, response_type="open_response",
        source_language="te")

    english = "I am Krishna Reddy, from Palem village."
    assert update_answer_translation(
        session_id=sid, question_number=5, english_translation=english,
        translation_status="translated", translation_engine="test-engine") is True

    ans = get_feedback_by_session(sid)["answers"][0]
    assert ans["transcript"] == TE_TRANSCRIPT            # original untouched
    assert ans["english_translation"] == english
    assert ans["translation_status"] == "translated"
    assert ans["translation_engine"] == "test-engine"
    assert ans["source_language"] == "te"


def test_translation_failure_and_retry(admin_conn, as_staff_a):
    from database.repository import (
        create_feedback_session,
        get_feedback_by_session,
        save_feedback_answer,
        update_answer_translation,
    )
    _clear_feedback(admin_conn)

    sid = create_feedback_session(language="hi")
    save_feedback_answer(
        session_id=sid, question_number=2, question_text="Symptoms?",
        transcript=HI_TRANSCRIPT, response_type="open_response",
        translation_status="pending", source_language="hi")

    # 1. Translation fails -> original still stored, status recorded as failed
    update_answer_translation(
        session_id=sid, question_number=2, english_translation="",
        translation_status="failed", translation_engine="test-engine")
    ans = get_feedback_by_session(sid)["answers"][0]
    assert ans["transcript"] == HI_TRANSCRIPT
    assert ans["translation_status"] == "failed"

    # 2. Retry succeeds later
    update_answer_translation(
        session_id=sid, question_number=2,
        english_translation="My name is Rameshwar Patel, Rampur village.",
        translation_status="translated", translation_engine="test-engine")
    ans = get_feedback_by_session(sid)["answers"][0]
    assert ans["translation_status"] == "translated"
    assert ans["english_translation"].startswith("My name is Rameshwar")


def test_english_input_marked_not_required(admin_conn, as_staff_a):
    from database.repository import create_feedback_session, get_feedback_by_session, save_feedback_answer
    _clear_feedback(admin_conn)

    sid = create_feedback_session(language="en")
    save_feedback_answer(
        session_id=sid, question_number=1, question_text="Name?",
        transcript="John Doe, Rampur", response_type="open_response",
        source_language="en")
    ans = get_feedback_by_session(sid)["answers"][0]
    assert ans["translation_status"] == "not_required"
    assert ans["english_translation"] == "John Doe, Rampur"
    assert ans["translation_engine"] == "identity_en"


# ---------------------------------------------------------------------------
# Pagination + CSV export
# ---------------------------------------------------------------------------
def test_pagination(admin_conn, as_staff_a):
    from database.repository import count_feedback_records, create_feedback_session, get_all_feedback_records
    _clear_feedback(admin_conn)

    for i in range(7):
        create_feedback_session(language="hi" if i % 2 else "te",
                                patient_code=f"PAT-TEST-{i:03d}")

    total = count_feedback_records()
    assert total == 7

    page1 = get_all_feedback_records(limit=3, offset=0)
    page2 = get_all_feedback_records(limit=3, offset=3)
    page3 = get_all_feedback_records(limit=3, offset=6)
    assert len(page1) == 3 and len(page2) == 3 and len(page3) == 1
    ids = [r["session_id"] for p in (page1, page2, page3) for r in p]
    assert len(ids) == len(set(ids)) == 7  # no overlaps, nothing lost

    # Server-side filters
    assert count_feedback_records(language="te") == 4
    assert count_feedback_records(language="hi") == 3
    assert count_feedback_records(search="PAT-TEST-004") == 1
    assert count_feedback_records(status="in_progress") == 7


def test_csv_export_bilingual(admin_conn, as_staff_a):
    from database.repository import create_feedback_session, get_all_feedback_records, save_feedback_answer
    _clear_feedback(admin_conn)

    sid = create_feedback_session(language="hi", patient_code="PAT-CSV-001")
    save_feedback_answer(
        session_id=sid, question_number=5, question_text="Suggestions?",
        transcript=HI_TRANSCRIPT, response_type="open_response",
        source_language="hi")

    records = get_all_feedback_records()
    assert records
    df = pd.DataFrame(records)
    df["original_transcript"] = df["transcript"]
    cols = ["session_id", "patient_code", "language", "question_number",
            "original_transcript", "english_translation", "translation_status"]
    csv_bytes = df[cols].to_csv(index=False).encode("utf-8")
    assert b"original_transcript" in csv_bytes
    assert b"english_translation" in csv_bytes

    rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8"))))
    assert rows[0] == cols
    assert rows[1][cols.index("original_transcript")] == HI_TRANSCRIPT


# ---------------------------------------------------------------------------
# Camp isolation (Row Level Security)
# ---------------------------------------------------------------------------
def test_camp_staff_cannot_see_other_camp(admin_conn, as_staff_a, as_staff_b):
    from database.context import set_auth_context, clear_auth_context
    from database.repository import (
        create_feedback_session,
        get_all_sessions,
        get_feedback_by_session,
        save_feedback_answer,
        update_answer_translation,
    )
    _clear_feedback(admin_conn)

    # Staff A creates a session with a private transcript
    set_auth_context(user_id=STAFF_A, camp_id=CAMP_A, role="camp_staff")
    sid = create_feedback_session(language="hi", patient_code="PAT-RLS-001")
    save_feedback_answer(
        session_id=sid, question_number=2, question_text="Symptoms?",
        transcript=HI_TRANSCRIPT, response_type="open_response",
        source_language="hi")
    clear_auth_context()

    # Staff B (other camp) must not see the session or its answer
    set_auth_context(user_id=STAFF_B, camp_id=CAMP_B, role="camp_staff")
    assert all(s["id"] != sid for s in get_all_sessions(limit=1000))
    assert get_feedback_by_session(sid) == {}
    assert update_answer_translation(
        session_id=sid, question_number=2, english_translation="leak",
        translation_status="translated") is False

    # Raw SQL as staff B: the transcript row is invisible and unwritable
    from database.pg import connect
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("select count(*) from public.feedback_answers where session_id = %s", (sid,))
        assert cur.fetchone()[0] == 0
        # RLS filters the UPDATE to zero rows (nothing changes)
        cur.execute(
            "update public.feedback_answers set transcript = 'tampered' "
            "where session_id = %s", (sid,))
        assert cur.rowcount == 0
        cur.execute("select count(*) from public.feedback_answers where session_id = %s", (sid,))
        assert cur.fetchone()[0] == 0
        # Cross-camp INSERT violates the WITH CHECK clause
        with pytest.raises(Exception):
            cur.execute(
                "insert into public.feedback_sessions (patient_code, language, camp_id) "
                "values ('PAT-EVIL', 'hi', %s)", (CAMP_A,))
            conn.commit()
        conn.rollback()
    finally:
        conn.close()
        clear_auth_context()


def test_admin_sees_all_camps(admin_conn, as_staff_a, as_admin):
    from database.context import set_auth_context, clear_auth_context
    from database.repository import create_feedback_session, get_all_sessions, get_feedback_by_session
    _clear_feedback(admin_conn)

    set_auth_context(user_id=STAFF_A, camp_id=CAMP_A, role="camp_staff")
    sid_a = create_feedback_session(language="hi", patient_code="PAT-ADM-A")
    clear_auth_context()

    set_auth_context(user_id=STAFF_B, camp_id=CAMP_B, role="camp_staff")
    sid_b = create_feedback_session(language="te", patient_code="PAT-ADM-B")
    clear_auth_context()

    # Staff A only sees camp A
    set_auth_context(user_id=STAFF_A, camp_id=CAMP_A, role="camp_staff")
    visible_a = {s["id"] for s in get_all_sessions(limit=1000)}
    clear_auth_context()
    assert sid_a in visible_a and sid_b not in visible_a

    # Unscoped administrator sees both camps
    set_auth_context(user_id=ADMIN_ALL, camp_id=None, role="admin")
    visible_admin = {s["id"] for s in get_all_sessions(limit=1000)}
    assert sid_a in visible_admin and sid_b in visible_admin
    assert get_feedback_by_session(sid_a) and get_feedback_by_session(sid_b)
    clear_auth_context()


def test_profiles_visibility(admin_conn, as_staff_a):
    """A staff user can read their own profile but not other profiles."""
    from database.pg import connect
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("select user_id, role, camp_id from public.profiles")
        rows = cur.fetchall()
        assert [str(r[0]) for r in rows] == [STAFF_A]
        assert rows[0][1] == "camp_staff" and str(rows[0][2]) == CAMP_A
    finally:
        conn.close()


def test_analytics_summary_is_rls_scoped(admin_conn, as_staff_a, as_staff_b):
    from database.context import set_auth_context, clear_auth_context
    from database.repository import create_feedback_session, get_analytics_summary
    _clear_feedback(admin_conn)

    set_auth_context(user_id=STAFF_A, camp_id=CAMP_A, role="camp_staff")
    for _ in range(2):
        create_feedback_session(language="hi")
    clear_auth_context()

    set_auth_context(user_id=STAFF_B, camp_id=CAMP_B, role="camp_staff")
    create_feedback_session(language="te")
    assert get_analytics_summary()["total_sessions"] == 1  # only camp B
    clear_auth_context()

    set_auth_context(user_id=STAFF_A, camp_id=CAMP_A, role="camp_staff")
    assert get_analytics_summary()["total_sessions"] == 2  # only camp A
    clear_auth_context()

    set_auth_context(user_id=ADMIN_ALL, camp_id=None, role="admin")
    assert get_analytics_summary()["total_sessions"] == 3  # everything
    clear_auth_context()
