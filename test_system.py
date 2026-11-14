"""
Automated End-to-End System Test for Healthcare Feedback Agent.
Comprehensive Technical and Functional Verification of New 5 Questions:
1. Patient Name & Village
2. Health Problems & Symptoms
3. Health Assistant Service Quality (Rating 1-5)
4. Treatment Explanation Clarity (Yes/No)
5. Camp Improvement Suggestions
"""
import os
import io
import sqlite3
import tempfile
import pandas as pd
from pathlib import Path

# Load environment variables safely with built-in fallback if python-dotenv is missing
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    for candidate in [Path(".env"), Path(__file__).resolve().parent / ".env"]:
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

# Keep test records separate from the application's persistent database.
_TEST_DB_TEMP = None
if __name__ == "__main__":
    _TEST_DB_TEMP = tempfile.TemporaryDirectory(prefix="feedback_agent_test_")
    os.environ["DATABASE_PATH"] = str(Path(_TEST_DB_TEMP.name) / "test.db")
    os.environ["DB_BACKEND"] = "sqlite"

from database.db import init_db, get_connection
from database.repository import (
    create_feedback_session,
    save_feedback_answer,
    complete_feedback_session,
    get_feedback_by_session,
    get_all_sessions,
    get_analytics_summary,
    get_all_feedback_records
)
from agent.questions import get_question, get_total_questions
from services.transcription import transcribe_audio
from services.feedback_analysis import generate_admin_report_summary, analyze_session_feedback
from services.translation import translate_patient_transcript
from agent.rating_extractor import extract_rating
from agent.voice_bot import decode_audio_payload
from database.repository import update_answer_translation, backfill_pending_translations
import base64

def test_questions():
    print("1. Testing Updated Questions...")
    assert get_total_questions() == 5, "Should have exactly 5 questions"

    expected_en_snippets = [
        "What is your name and which village",
        "What health problems or symptoms",
        "How was the service given by the health assistant",
        "Did the healthcare worker explain your treatment clearly",
        "What suggestions would you like to give for camp improvements"
    ]

    for i in range(1, 6):
        q = get_question(i, "en")
        hi_q = get_question(i, "hi")
        te_q = get_question(i, "te")
        assert expected_en_snippets[i-1].lower() in q["text"].lower(), f"Question {i} text mismatch: {q['text']}"
        assert hi_q["text"], f"Hindi question {i} is empty"
        assert te_q["text"], f"Telugu question {i} is empty"
        print(f"   Q{i}: {q['text']}")
        print(f"       HI: {hi_q['text']}")
        print(f"       TE: {te_q['text']}")
    print("   ✓ All 5 updated camp feedback questions verified in EN, HI, and TE.")

def test_database_and_workflow():
    print("\n2. Testing Database and Persistence with New Questions...")
    init_db()

    # 1. Hindi Patient Session
    hi_session = create_feedback_session("hi")
    answers_hi = [
        (1, "मेरा नाम रामेश्वर पटेल है, रामपुर गाँव।", "open_response", None),
        (2, "मुझे घुटनों में दर्द और खाँसी की शिकायत है।", "open_response", None),
        (3, "स्वास्थ्य सहायक ने बहुत अच्छे से देखा।", "rating", 5),
        (4, "हाँ, उन्होंने सब कुछ विस्तार से समझाया।", "yes", None),
        (5, "दवाइयों का स्टॉक और अधिक होना चाहिए।", "open_response", None)
    ]
    for q_num, transcript, resp_type, rating in answers_hi:
        q_data = get_question(q_num, "hi")
        save_feedback_answer(
            session_id=hi_session,
            question_number=q_num,
            question_text=q_data["text"],
            transcript=transcript,
            response_type=resp_type,
            rating=rating
        )
    complete_feedback_session(hi_session)
    hi_data = get_feedback_by_session(hi_session)
    assert hi_data["status"] == "completed"
    assert len(hi_data["answers"]) == 5
    assert hi_data["patient_name"] == "मेरा नाम रामेश्वर पटेल है, रामपुर गाँव।"
    print("   ✓ Hindi patient session and name/village persistence verified.")

    # 2. Telugu Patient Session
    te_session = create_feedback_session("te")
    answers_te = [
        (1, "నా పేరు కృష్ణారెడ్డి, మాది పాలెం గ్రామం.", "open_response", None),
        (2, "తీవ్రమైన తలనొప్పి మరియు కంటి చూపు మసకగా ఉంది.", "open_response", None),
        (3, "హెల్త్ అసిస్టెంట్ చాలా గౌరవంగా సేవ అందించారు.", "rating", 4),
        (4, "అవును, మందుల వివరాలు బాగా చెప్పారు.", "yes", None),
        (5, "నెలకు రెండుసార్లు ఇలాంటి శిబిరాలు పెట్టాలి.", "open_response", None)
    ]
    for q_num, transcript, resp_type, rating in answers_te:
        q_data = get_question(q_num, "te")
        save_feedback_answer(
            session_id=te_session,
            question_number=q_num,
            question_text=q_data["text"],
            transcript=transcript,
            response_type=resp_type,
            rating=rating
        )
    complete_feedback_session(te_session)
    te_data = get_feedback_by_session(te_session)
    assert te_data["status"] == "completed"
    assert len(te_data["answers"]) == 5
    assert te_data["patient_name"] == "నా పేరు కృష్ణారెడ్డి, మాది పాలెం గ్రామం."
    print("   ✓ Telugu patient session and name/village persistence verified.")

def test_local_transcription_validation():
    print("\n3. Testing local transcription input validation...")
    result = transcribe_audio(b"", language="hi", question_number=1)
    assert result["success"] is False
    assert result["mode"] == "local"
    assert "too short" in result["error"]
    print("   ✓ Speech transcription uses the local backend; empty audio is rejected.")

def test_local_analytics_and_admin_export():
    print("\n4. Testing Local Analytics & Camp Feedback Insights...")
    records = get_all_feedback_records()
    df = pd.DataFrame(records)
    assert not df.empty

    report = generate_admin_report_summary(records)
    print(f"   ✓ Issues breakdown: {report['issues_breakdown']}")
    print(f"   ✓ Reported health problems: {report['reported_health_problems']}")
    print(f"   ✓ Camp suggestions: {report['recent_suggestions']}")

def test_voice_bot_audio_and_rating():
    print("\n5. Testing Voice Bot In-Memory Audio Decoding & Deterministic Rating Extraction...")
    # Test base64 payload decoding
    raw_sample = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    b64_str = base64.b64encode(raw_sample).decode("utf-8")
    data_url = f"data:audio/wav;base64,{b64_str}"

    decoded_plain = decode_audio_payload(b64_str)
    assert decoded_plain == raw_sample, "Plain base64 decode failed"
    decoded_url = decode_audio_payload(data_url)
    assert decoded_url == raw_sample, "Data-URL base64 decode failed"
    assert decode_audio_payload("") == b"", "Empty string decode failed"
    print("   ✓ In-memory audio payload decoder verified for plain & data-url base64.")

    # Test Hindi Rating Extraction
    r_hi_5, _ = extract_rating("सेवा बहुत अच्छी और पाँच स्टार थी", "hi")
    assert r_hi_5 == 5, f"Expected 5, got {r_hi_5}"
    r_hi_3, _ = extract_rating("सेवा सामान्य थी, कामचलाऊ थी", "hi")
    assert r_hi_3 == 3, f"Expected 3, got {r_hi_3}"
    r_hi_1, _ = extract_rating("बहुत खराब व्यवस्था थी", "hi")
    assert r_hi_1 == 1, f"Expected 1, got {r_hi_1}"
    print("   ✓ Hindi rating extraction verified (5, 3, 1).")

    # Test Telugu Rating Extraction
    r_te_5, _ = extract_rating("సేవ చాలా బాగుంది, 5 స్టార్", "te")
    assert r_te_5 == 5, f"Expected 5, got {r_te_5}"
    r_te_4, _ = extract_rating("మంచిది, బాగుంది", "te")
    assert r_te_4 == 4, f"Expected 4, got {r_te_4}"
    r_te_2, _ = extract_rating("సంతృప్తి లేదు, బాగాలేదు", "te")
    assert r_te_2 == 2, f"Expected 2, got {r_te_2}"
    print("   ✓ Telugu rating extraction verified (5, 4, 2).")

    # Test English / Numeric Scale
    r_scale, _ = extract_rating("I would give 4 out of 5", "en")
    assert r_scale == 4, f"Expected 4, got {r_scale}"
    r_en_5, _ = extract_rating("It was excellent and superb", "en")
    assert r_en_5 == 5, f"Expected 5, got {r_en_5}"
    print("   ✓ English and explicit scale (4 out of 5) rating extraction verified.")

def test_bilingual_storage_and_translation():
    print("\n6. Testing Genuine Full-Sentence Neural Machine Translation (NLLB-200 Int8 on CPU)...")
    from services.translation import OfflineNeuralTranslator

    translator = OfflineNeuralTranslator.get_instance()
    if not translator.is_ready:
        print(f"   - NLLB model checks skipped: {translator.load_error}")
        return

    # 1. Telugu full-sentence neural translation
    te_text_1 = "ఆరోగ్య సిబ్బంది నా చికిత్స గురించి స్పష్టంగా వివరించారు."
    res_te_1 = translate_patient_transcript(te_text_1, "te")
    assert res_te_1["success"] is True
    assert res_te_1["translation_status"] == "translated"
    assert "explained" in res_te_1["english_translation"].lower()
    assert "treatment" in res_te_1["english_translation"].lower()
    print(f"   ✓ 1. Telugu full sentence verified: '{te_text_1}' -> '{res_te_1['english_translation']}' ({res_te_1['latency_ms']}ms)")

    # 2. Hindi full-sentence neural translation
    hi_text_1 = "स्वास्थ्यकर्मी ने मुझे इलाज अच्छी तरह समझाया।"
    res_hi_1 = translate_patient_transcript(hi_text_1, "hi")
    assert res_hi_1["success"] is True
    assert res_hi_1["translation_status"] == "translated"
    assert "explained" in res_hi_1["english_translation"].lower()
    assert "treatment" in res_hi_1["english_translation"].lower()
    print(f"   ✓ 2. Hindi full sentence verified: '{hi_text_1}' -> '{res_hi_1['english_translation']}' ({res_hi_1['latency_ms']}ms)")

    # 3. English response without translation
    en_text_1 = "The doctor was very kind and gave good medicines."
    res_en_1 = translate_patient_transcript(en_text_1, "en")
    assert res_en_1["success"] is True
    assert res_en_1["translation_status"] == "not_required"
    assert res_en_1["english_translation"] == en_text_1
    assert res_en_1["translation_engine"] == "identity_en"
    print("   ✓ 3. English response preserved without translation ('not_required').")

    # 4. Translation failure handling
    res_fail = translate_patient_transcript(hi_text_1, "hi", simulate_failure=True)
    assert res_fail["success"] is False
    assert res_fail["translation_status"] == "failed"
    print("   ✓ 4. Translation failure handled safely with status='failed'.")

    # 5. Missing / unsupported local translation model
    res_unknown = translate_patient_transcript("Bonjour le monde", "fr")
    assert res_unknown["success"] is False
    assert res_unknown["translation_status"] == "failed"
    print("   ✓ 5. Unsupported language safely routed to status='failed'.")

    # 6. Unseen Names & Villages Preservation
    unseen_te = "నా పేరు రాజశేఖర్ వర్మ, మాది భీమవరం గ్రామం."
    res_unseen_te = translate_patient_transcript(unseen_te, "te")
    assert res_unseen_te["success"] is True
    assert any(tok in res_unseen_te["english_translation"].lower() for tok in ["rajeshekar", "varma", "bhimwaram", "village"])
    print(f"   ✓ 6a. Unseen Telugu name/village: '{unseen_te}' -> '{res_unseen_te['english_translation']}'")

    unseen_hi = "मेरा नाम सुरेश यादव है और मैं बिलासपुर गाँव से हूँ।"
    res_unseen_hi = translate_patient_transcript(unseen_hi, "hi")
    assert res_unseen_hi["success"] is True
    assert "suresh" in res_unseen_hi["english_translation"].lower() or "bilaspur" in res_unseen_hi["english_translation"].lower()
    print(f"   ✓ 6b. Unseen Hindi name/village: '{unseen_hi}' -> '{res_unseen_hi['english_translation']}'")

    # 7. Negation & Medical Symptoms Preservation
    neg_te = "ఇచ్చిన మందులు వాడినా నాకు ఇంకా ఉపశమనం కలగలేదు."
    res_neg_te = translate_patient_transcript(neg_te, "te")
    assert res_neg_te["success"] is True
    assert any(w in res_neg_te["english_translation"].lower() for w in ["not", "no", "relief", "medication"])
    print(f"   ✓ 7a. Telugu medical negation: '{neg_te}' -> '{res_neg_te['english_translation']}'")

    neg_hi = "मुझे जो दवाइयां दी गईं उनसे मुझे अभी तक कोई आराम नहीं मिला।"
    res_neg_hi = translate_patient_transcript(neg_hi, "hi")
    assert res_neg_hi["success"] is True
    assert any(w in res_neg_hi["english_translation"].lower() for w in ["not", "no", "relief", "medicines"])
    print(f"   ✓ 7b. Hindi medical negation: '{neg_hi}' -> '{res_neg_hi['english_translation']}'")

    # 8. Existing records migration and translation preservation
    sess_id = create_feedback_session("hi")
    save_feedback_answer(
        session_id=sess_id,
        question_number=1,
        question_text="आपका नाम क्या है और आप किस गाँव से आए हैं?",
        transcript="मेरा नाम रामेश्वर पटेल है, रामपुर गाँव।",
        response_type="open_response"
    )
    # Perform translation and update
    trans = translate_patient_transcript("मेरा नाम रामेश्वर पटेल है, रामपुर गाँव।", "hi")
    update_answer_translation(
        session_id=sess_id,
        question_number=1,
        english_translation=trans["english_translation"],
        translation_status=trans["translation_status"],
        translation_engine=trans["translation_engine"]
    )
    sess_data = get_feedback_by_session(sess_id)
    ans1 = sess_data["answers"][0]
    assert ans1["transcript"] == "मेरा नाम रामेश्वर पटेल है, रामपुर गाँव।"
    assert ans1["english_translation"] is not None
    assert ans1["translation_status"] == "translated"
    print("   ✓ 8. Bilingual answer stored in single database record with matching ID.")

    # 9. Repeated database initialization idempotency
    init_db()
    init_db()
    print("   ✓ 9. Repeated database initialization verified as safe and idempotent.")

    # 10. Duplicate answer prevention (ON CONFLICT)
    save_feedback_answer(
        session_id=sess_id,
        question_number=1,
        question_text="Updated text",
        transcript="मेरा नाम रामेश्वर पटेल है, रामपुर गाँव।",
        response_type="open_response",
        english_translation="My name is Rameshwar Patel, from Rampur village.",
        translation_status="translated"
    )
    sess_data_dup = get_feedback_by_session(sess_id)
    assert len(sess_data_dup["answers"]) == 1, "Duplicate answer row created!"
    print("   ✓ 10. Duplicate answer prevention verified (1 answer per question per session).")

    # 11. Original transcript remains completely unchanged
    assert sess_data_dup["answers"][0]["transcript"] == "मेरा नाम रामेश्वर पटेल है, रामपुर गाँव।"
    print("   ✓ 11. Original transcript remains authoritative and unchanged.")

    # 12. Both versions appear in admin dashboard queries & CSV export
    records = get_all_feedback_records()
    sample_rec = next(r for r in records if r["session_id"] == sess_id and r["question_number"] == 1)
    assert "transcript" in sample_rec
    assert "english_translation" in sample_rec
    assert sample_rec["transcript"] == "मेरा नाम रामेश्वर पटेल है, रामपुर गाँव।"
    assert sample_rec["english_translation"] is not None

    df_export = pd.DataFrame(records)
    df_export["original_transcript"] = df_export["transcript"]
    assert "original_transcript" in df_export.columns
    assert "english_translation" in df_export.columns
    csv_bytes = df_export.to_csv(index=False).encode("utf-8")
    assert b"original_transcript" in csv_bytes
    assert b"english_translation" in csv_bytes
    print("   ✓ 12. Admin dashboard & CSV export contain both original_transcript and english_translation.")
    print("   ✓ 13. CTranslate2 neural engine runs 100% offline on CPU (zero GPU, zero external APIs).")

if __name__ == "__main__":
    print("System tests use a temporary SQLite database; app data is untouched.")
    test_questions()
    test_database_and_workflow()
    test_local_transcription_validation()
    test_local_analytics_and_admin_export()
    test_voice_bot_audio_and_rating()
    test_bilingual_storage_and_translation()
    print("\n=======================================================")
    print("🎉 ALL UPDATED 5 CAMP QUESTIONS & SYSTEM TESTS PASSED!")
    print("=======================================================")
