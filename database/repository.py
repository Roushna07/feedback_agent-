"""
Repository operations for feedback sessions and answers.

Backend-agnostic: the same SQL runs on the existing SQLite database and on
Supabase PostgreSQL (see database/pg.py). RLS on PostgreSQL additionally
enforces camp isolation even if a caller forgets a filter.
"""
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from .db import get_connection
from .context import DEFAULT_CAMP_ID, get_auth_context

def generate_patient_code() -> str:
    """Generate an anonymous patient code."""
    now_str = datetime.now().strftime("%y%m%d")
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"PAT-{now_str}-{short_uuid}"

def _resolve_camp_id(camp_id: Optional[str] = None) -> str:
    """Camp for a new session: explicit -> signed-in user's camp -> default."""
    if camp_id:
        return camp_id
    ctx_camp = get_auth_context().get("camp_id")
    if ctx_camp:
        return ctx_camp
    return DEFAULT_CAMP_ID

def create_feedback_session(
    language: str,
    patient_code: Optional[str] = None,
    consent_given: bool = True,
    patient_name: Optional[str] = None,
    village: Optional[str] = None,
    camp_id: Optional[str] = None
) -> int:
    """Create a new feedback session and return its ID."""
    if not patient_code:
        patient_code = generate_patient_code()

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO feedback_sessions (patient_code, patient_name, village, language, consent_given, status, camp_id, created_at)
            VALUES (?, ?, ?, ?, ?, 'in_progress', ?, CURRENT_TIMESTAMP)
            """,
            (patient_code, patient_name, village, language, consent_given, _resolve_camp_id(camp_id))
        )
        session_id = cursor.lastrowid
        conn.commit()
        return session_id
    finally:
        conn.close()

def save_feedback_answer(
    session_id: int,
    question_number: int,
    question_text: str,
    transcript: str,
    response_type: str,
    rating: Optional[int] = None,
    english_translation: Optional[str] = None,
    translation_status: str = "pending",
    translation_engine: Optional[str] = None,
    source_language: Optional[str] = None
) -> int:
    """
    Save or update a confirmed feedback answer for a specific question in a session.
    Stores both the original transcript and the English translation.
    Uses ON CONFLICT DO UPDATE to ensure no duplicate answers per question in a session.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Determine source language from session if not provided
        if not source_language:
            cursor.execute("SELECT language FROM feedback_sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()
            source_language = row[0] if row else "hi"

        # For English input, translation is not required
        if source_language == "en":
            english_translation = transcript
            translation_status = "not_required"
            translation_engine = "identity_en"

        cursor.execute(
            """
            INSERT INTO feedback_answers (
                session_id, question_number, question_text, transcript, response_type, rating,
                english_translation, translation_status, translation_engine, source_language, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(session_id, question_number) DO UPDATE SET
                question_text=excluded.question_text,
                transcript=excluded.transcript,
                response_type=excluded.response_type,
                rating=excluded.rating,
                english_translation=excluded.english_translation,
                translation_status=excluded.translation_status,
                translation_engine=excluded.translation_engine,
                source_language=excluded.source_language,
                created_at=CURRENT_TIMESTAMP
            """,
            (
                session_id, question_number, question_text, transcript, response_type, rating,
                english_translation, translation_status, translation_engine, source_language
            )
        )
        answer_id = cursor.lastrowid

        # If this is Question 1 (Name and Village), update session record
        if question_number == 1 and transcript:
            cursor.execute(
                "UPDATE feedback_sessions SET patient_name = ? WHERE id = ?",
                (transcript, session_id)
            )

        conn.commit()
        return answer_id
    finally:
        conn.close()

def update_answer_translation(
    session_id: int,
    question_number: int,
    english_translation: str,
    translation_status: str = "translated",
    translation_engine: Optional[str] = None
) -> bool:
    """
    Update the English translation and status of an already persisted feedback answer.
    Preserves the original transcript and never alters other answer fields.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE feedback_answers
            SET english_translation = ?,
                translation_status = ?,
                translation_engine = ?
            WHERE session_id = ? AND question_number = ?
            """,
            (english_translation, translation_status, translation_engine, session_id, question_number)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

def complete_feedback_session(session_id: int) -> bool:
    """Mark a feedback session as completed."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE feedback_sessions
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (session_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

def get_feedback_by_session(session_id: int) -> Dict[str, Any]:
    """Retrieve full session details and its answers."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM feedback_sessions WHERE id = ?", (session_id,))
        session_row = cursor.fetchone()
        if not session_row:
            return {}

        session_data = dict(session_row)

        cursor.execute(
            "SELECT * FROM feedback_answers WHERE session_id = ? ORDER BY question_number ASC",
            (session_id,)
        )
        answers = [dict(row) for row in cursor.fetchall()]
        session_data["answers"] = answers
        return session_data
    finally:
        conn.close()

def get_all_sessions(limit: int = 200, status: Optional[str] = None, camp_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get recent sessions with optional status/camp filters."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = "SELECT * FROM feedback_sessions"
        clauses, params = [], []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if camp_id:
            clauses.append("camp_id = ?")
            params.append(camp_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, tuple(params))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def _record_filters(
    language: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    date_prefix: Optional[str] = None,
):
    clauses, params = [], []
    if language:
        clauses.append("s.language = ?")
        params.append(language)
    if status:
        clauses.append("s.status = ?")
        params.append(status)
    if date_prefix:
        # Works on SQLite text timestamps (UTC) and on timestamptz (UTC session)
        clauses.append("s.created_at >= ? AND s.created_at <= ?")
        params.extend([f"{date_prefix} 00:00:00", f"{date_prefix} 23:59:59"])
    if search:
        like = f"%{str(search).lower()}%"
        clauses.append(
            "(lower(s.patient_code) LIKE ? OR lower(coalesce(s.patient_name, '')) LIKE ?"
            " OR lower(coalesce(s.village, '')) LIKE ?"
            " OR lower(a.transcript) LIKE ? OR lower(coalesce(a.english_translation, '')) LIKE ?)"
        )
        params.extend([like, like, like, like, like])
    return clauses, params


_RECORD_SELECT = """
    SELECT
        s.id AS session_id,
        s.patient_code,
        s.patient_name,
        s.village,
        s.language,
        s.camp_id,
        s.status AS session_status,
        s.created_at AS session_date,
        s.completed_at,
        a.id AS answer_id,
        a.question_number,
        a.question_text,
        a.transcript,
        a.response_type,
        a.rating,
        a.english_translation,
        a.translation_status,
        a.translation_engine,
        COALESCE(a.source_language, s.language) AS source_language,
        a.created_at AS answer_time
    FROM feedback_sessions s
    LEFT JOIN feedback_answers a ON s.id = a.session_id
"""


def get_all_feedback_records(
    limit: Optional[int] = None,
    offset: int = 0,
    language: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    date_prefix: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Get joined session and answer records for reporting.
    Supports server-side pagination (limit/offset) and dashboard filters so
    large datasets never need to be fully materialised.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        clauses, params = _record_filters(language, status, search, date_prefix)
        where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        query = (
            _RECORD_SELECT
            + where_sql
            + " ORDER BY s.id DESC, a.question_number ASC"
        )
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params = list(params) + [int(limit), int(offset)]
        cursor.execute(query, tuple(params))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def count_feedback_records(
    language: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    date_prefix: Optional[str] = None,
) -> int:
    """Total number of joined session/answer rows matching the filters."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        clauses, params = _record_filters(language, status, search, date_prefix)
        where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        cursor.execute(
            "SELECT COUNT(*) FROM feedback_sessions s"
            " LEFT JOIN feedback_answers a ON s.id = a.session_id"
            + where_sql,
            tuple(params),
        )
        row = cursor.fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    finally:
        conn.close()

def get_analytics_summary() -> Dict[str, Any]:
    """Calculate key analytics metrics."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM feedback_sessions")
        total_sessions = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM feedback_sessions WHERE status = 'completed'")
        completed_sessions = cursor.fetchone()[0] or 0

        incomplete_sessions = total_sessions - completed_sessions

        cursor.execute("SELECT COUNT(*) FROM feedback_sessions WHERE language = 'hi'")
        hindi_sessions = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM feedback_sessions WHERE language = 'te'")
        telugu_sessions = cursor.fetchone()[0] or 0

        cursor.execute("SELECT AVG(rating) FROM feedback_answers WHERE rating IS NOT NULL")
        avg_rating_res = cursor.fetchone()[0]
        avg_satisfaction = round(avg_rating_res, 2) if avg_rating_res is not None else 0.0

        return {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "incomplete_sessions": incomplete_sessions,
            "hindi_sessions": hindi_sessions,
            "telugu_sessions": telugu_sessions,
            "avg_satisfaction": avg_satisfaction
        }
    finally:
        conn.close()

def backfill_pending_translations(limit: int = 200, force_retranslate: bool = False) -> int:
    """
    Safely backfill translations for pre-existing answers using genuine neural NLLB translation.
    Preserves all original transcripts.
    """
    from services.translation import translate_patient_transcript, MODEL_IDENTIFIER

    conn = get_connection()
    try:
        cursor = conn.cursor()
        if force_retranslate:
            cursor.execute(
                """
                SELECT a.session_id, a.question_number, a.transcript, COALESCE(a.source_language, s.language) AS lang
                FROM feedback_answers a
                JOIN feedback_sessions s ON a.session_id = s.id
                WHERE (a.translation_engine != ? OR a.translation_engine IS NULL)
                  AND COALESCE(a.source_language, s.language) != 'en'
                LIMIT ?
                """,
                (MODEL_IDENTIFIER, limit)
            )
        else:
            cursor.execute(
                """
                SELECT a.session_id, a.question_number, a.transcript, COALESCE(a.source_language, s.language) AS lang
                FROM feedback_answers a
                JOIN feedback_sessions s ON a.session_id = s.id
                WHERE a.translation_status = 'pending' OR a.english_translation IS NULL
                LIMIT ?
                """,
                (limit,)
            )
        rows = cursor.fetchall()
        updated_count = 0
        for row in rows:
            sid, q_num, transcript, lang = row[0], row[1], row[2], row[3]
            res = translate_patient_transcript(transcript, lang)
            if res["success"]:
                cursor.execute(
                    """
                    UPDATE feedback_answers
                    SET english_translation = ?,
                        translation_status = ?,
                        translation_engine = ?
                    WHERE session_id = ? AND question_number = ?
                    """,
                    (res["english_translation"], res["translation_status"], res["translation_engine"], sid, q_num)
                )
                updated_count += 1
            else:
                cursor.execute(
                    """
                    UPDATE feedback_answers
                    SET translation_status = 'failed',
                        translation_engine = ?
                    WHERE session_id = ? AND question_number = ?
                    """,
                    (res.get("translation_engine", "none"), sid, q_num)
                )
        conn.commit()
        return updated_count
    finally:
        conn.close()
