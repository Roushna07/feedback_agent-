"""
Patient Conversation Controller for the Multilingual Voice Interview Bot.
Implements a guided 5-question patient interview:
1. Staff selects language (Hindi/Telugu) and clicks START BOT.
2. Bot speaks each question via browser Web Speech API (hi-IN / te-IN).
3. Bot automatically starts microphone recording when speech ends.
4. User manually stops recording and reviews/corrects the transcript.
5. Audio is transcribed locally with Faster-Whisper on the CPU.
6. The answer is translated to English before it is stored.
7. Staff controls are provided for Pause, Resume, Repeat, Manual Correction, and End Interview.
"""
from typing import Any, Dict, Optional
import streamlit as st
from .questions import get_question, get_total_questions, get_ui_string
from .state_manager import start_new_session, reset_session_state
from .voice_bot import render_voice_bot, decode_audio_payload
from .rating_extractor import extract_rating
from services.transcription import transcribe_audio
from services.local_transcription import get_local_stt_model_name
from services.translation import translate_patient_transcript
from database.repository import save_feedback_answer, complete_feedback_session


def _translate_and_save_english_answer(
    session_id: int,
    question_number: int,
    question_text: str,
    answer_text: str,
    response_type: str,
    rating: Optional[int],
    source_language: str
) -> Dict[str, Any]:
    try:
        translation = translate_patient_transcript(
            answer_text,
            source_language=source_language
        )
    except Exception as exc:
        return {"success": False, "error": str(exc)}

    english_text = (translation.get("english_translation") or "").strip()
    if not translation.get("success") or not english_text:
        return {
            "success": False,
            "error": translation.get("error") or "No English translation was produced."
        }

    translation_status = translation.get("translation_status", "translated")
    translation_engine = translation.get("translation_engine")
    try:
        save_feedback_answer(
            session_id=session_id,
            question_number=question_number,
            question_text=question_text,
            transcript=english_text,
            response_type=response_type,
            rating=rating,
            english_translation=english_text,
            translation_status=translation_status,
            translation_engine=translation_engine,
            source_language=source_language
        )
    except Exception as exc:
        return {"success": False, "error": str(exc)}

    return {
        "success": True,
        "english_translation": english_text,
        "translation_status": translation_status,
        "translation_engine": translation_engine,
    }

def render_welcome_and_consent():
    """Step 1: Language selection, welcome message, and Start Bot action."""
    lang = st.session_state.get("language", "hi")

    st.markdown(f"""
    <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 18px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.03); margin-bottom: 20px;">
        <div style="font-size: 0.75rem; font-weight: 700; color: #0D9488; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px;">
            🤖 Multilingual Conversational Agent
        </div>
        <h2 style="color: #0F172A; font-size: 1.45rem; font-weight: 800; margin: 0 0 8px 0;">{get_ui_string('title', lang)}</h2>
        <p style="color: #64748B; font-size: 0.88rem; line-height: 1.5; margin: 0;">{get_ui_string('subtitle', lang)}</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🇮🇳 हिंदी (Hindi)", width="stretch", type="primary" if lang == "hi" else "secondary"):
            st.session_state.language = "hi"
            st.rerun()
    with col2:
        if st.button("🇮🇳 తెలుగు (Telugu)", width="stretch", type="primary" if lang == "te" else "secondary"):
            st.session_state.language = "te"
            st.rerun()

    st.divider()

    st.info(
        f"Speech transcription runs locally on this computer with Whisper "
        f"({get_local_stt_model_name()}). The first recording may download the "
        "model; patient audio is not uploaded."
    )

    # Welcome Card with English translation
    st.info(get_ui_string("welcome", lang))

    st.markdown(f"### {get_ui_string('consent_question', lang)}")
    st.caption("💡 *The automated bot will speak questions aloud and record answers. Tap Stop Recording when the answer is complete.*")

    col_c1, col_c2 = st.columns([2, 1])
    with col_c1:
        start_btn_label = (
            "🚀 START AUTOMATED BOT (ऑटोमेटेड बॉट शुरू करें)"
            if lang == "hi" else
            "🚀 START AUTOMATED BOT (ఆటోమేటెడ్ బాట్‌ను ప్రారంభించండి)"
        )
        if st.button(start_btn_label, width="stretch", type="primary"):
            start_new_session(language=lang)
            st.rerun()
    with col_c2:
        if st.button(get_ui_string("consent_no", lang), width="stretch"):
            st.warning("Interview declined. Select language above when ready to begin.")

def render_completion_screen():
    """Step 4: Thank you message, completion celebration, and session summary."""
    lang = st.session_state.get("language", "hi")
    st.balloons()
    patient_code = st.session_state.get("patient_code", "N/A")

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #0F172A 0%, #134E4A 100%); border-radius: 20px; padding: 28px; color: white; margin-bottom: 24px; box-shadow: 0 4px 16px rgba(0,0,0,0.1);">
        <div style="display: inline-block; background: rgba(16,185,129,0.2); border: 1px solid rgba(16,185,129,0.4); color: #6EE7B7; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 700; margin-bottom: 10px;">
            🎉 Interview Completed Successfully
        </div>
        <h2 style="color: white; margin: 0 0 8px 0; font-size: 1.6rem; font-weight: 800;">{get_ui_string('thank_you_title', lang)}</h2>
        <p style="color: #CBD5E1; font-size: 0.95rem; margin: 0; line-height: 1.5;">{get_ui_string('thank_you_msg', lang)}</p>
        <div style="margin-top: 16px; padding-top: 14px; border-top: 1px solid rgba(255,255,255,0.1); display: flex; gap: 16px; font-size: 0.82rem;">
            <span>Patient ID: <strong>{patient_code}</strong></span>
            <span>•</span>
            <span>Persistence: <strong style="color: #6EE7B7;">Saved in local SQLite</strong></span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Display summary of all 5 answers
    st.subheader("📋 Recorded Interview Responses (दर्ज किए गए उत्तर)")
    answers = st.session_state.get("answers_recorded", {})
    for q_num in range(1, get_total_questions() + 1):
        q_data = get_question(q_num, lang)
        ans_data = answers.get(q_num, {})
        with st.expander(f"Question {q_num}: {q_data.get('text', '')}", expanded=True):
            st.caption(f"🌐 Question (English): {q_data.get('en_text', '')}")
            transcript_txt = ans_data.get("transcript", "(No answer recorded)")
            st.info(f"🗣️ **Original Response ({lang.upper()}):** {transcript_txt}")

            eng_trans = ans_data.get("english_translation")
            if eng_trans:
                st.success(f"🌐 **English Translation (Meta NLLB-200):** {eng_trans}")
            elif ans_data.get("translation_status") == "failed":
                st.caption("⚠️ *Translation pending/unavailable*")

            if ans_data.get("rating"):
                st.write(f"⭐ **Extracted Rating:** {ans_data['rating']} / 5")

    st.divider()
    new_btn_label = "🚀 Start New Patient Interview (नया साक्षात्कार शुरू करें)" if lang == "hi" else "🚀 Start New Patient Interview (కొత్త ఇంటర్వ్యూ ప్రారంభించండి)"
    if st.button(new_btn_label, width="stretch", type="primary"):
        reset_session_state()
        st.rerun()

def render_conversation_step():
    """Step 2 & 3: Fully Automated Conversational Voice Bot Step."""
    lang = st.session_state.get("language", "hi")
    total_q = get_total_questions()
    current_q_num = st.session_state.get("current_question_index", 1)
    session_id = st.session_state.get("session_id")
    patient_code = st.session_state.get("patient_code")

    if not session_id or not st.session_state.get("consent_given"):
        render_welcome_and_consent()
        return

    if st.session_state.get("is_completed", False) or current_q_num > total_q:
        render_completion_screen()
        return

    # Header & Progress
    progress_val = float(current_q_num) / float(total_q)
    st.progress(progress_val)
    st.caption(get_ui_string("question_progress", lang, current=current_q_num, total=total_q) + f" | ID: {patient_code}")

    # Current Question Data
    q_data = get_question(current_q_num, lang)
    q_text = q_data.get("text", "")
    en_text = q_data.get("en_text", "")
    q_type = q_data.get("type", "open_response")

    # Staff Control Toolbar
    with st.expander("🛠️ Staff Controls (स्टाफ नियंत्रण / సిబ్బంది నియంత్రణ)", expanded=False):
        c_ctrl1, c_ctrl2, c_ctrl3, c_ctrl4 = st.columns(4)
        with c_ctrl1:
            if st.session_state.get("bot_state") == "PAUSED":
                if st.button("▶️ Resume Bot", width="stretch"):
                    st.session_state.bot_state = "SPEAKING_QUESTION"
                    st.session_state.bot_command = "resume"
                    st.rerun()
            else:
                if st.button("⏸️ Pause Bot", width="stretch"):
                    st.session_state.bot_state = "PAUSED"
                    st.session_state.bot_command = "pause"
                    st.rerun()
        with c_ctrl2:
            if st.button("🔁 Repeat Question", width="stretch"):
                st.session_state.bot_command = "repeat"
                st.session_state.bot_state = "SPEAKING_QUESTION"
                st.rerun()
        with c_ctrl3:
            manual_toggle = st.button("✏️ Toggle Manual Edit", width="stretch")
            if manual_toggle:
                st.session_state.manual_edit_mode = not st.session_state.get("manual_edit_mode", False)
                st.rerun()
        with c_ctrl4:
            if st.button("⏹️ End Interview", width="stretch"):
                complete_feedback_session(session_id)
                st.session_state.is_completed = True
                st.rerun()

    if st.session_state.get("bot_state") == "PAUSED":
        st.warning("⏸️ **Interview Paused by Staff.** Click 'Resume Bot' in staff controls above to continue.")

    # Prominent Question Display Card
    st.markdown(
        f"""
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-left: 6px solid #0D9488; border-radius: 16px; padding: 22px 26px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.04);">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                <span style="font-size: 0.78rem; font-weight: 700; color: #0D9488; text-transform: uppercase; letter-spacing: 0.05em; background: #F0FDFA; padding: 4px 10px; border-radius: 6px; border: 1px solid #CCFBF1;">
                    Question {current_q_num} of {total_q}
                </span>
                <span style="font-size: 0.78rem; color: #94A3B8; font-weight: 500;">
                    ID: {patient_code}
                </span>
            </div>
            <h3 style="color: #0F172A; margin: 0 0 12px 0; font-size: 1.35rem; font-weight: 700; line-height: 1.4;">{q_text}</h3>
            <div style="background: #F8FAFC; border: 1px solid #E2E8F0; padding: 10px 14px; border-radius: 10px; display: inline-flex; align-items: center; gap: 8px;">
                <span style="color: #0D9488; font-size: 0.85rem; font-weight: 700;">🌐 English:</span>
                <span style="color: #334155; font-size: 0.88rem; font-weight: 500;">{en_text}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 1. RENDER AUTOMATED VOICE BOT COMPONENT
    bot_payload = render_voice_bot(
        question_number=current_q_num,
        question_text=q_text,
        language=lang,
        is_bot_active=st.session_state.get("bot_active", True),
        command=st.session_state.get("bot_command", "speak_and_listen"),
        key=f"voice_bot_q_{current_q_num}"
    )

    # 2. HANDLE BROWSER BOT PAYLOAD (AUDIO RECORDED / SILENCE DETECTED)
    if bot_payload and isinstance(bot_payload, dict):
        action = bot_payload.get("action")
        payload_id = f"{current_q_num}_{action}_{bot_payload.get('duration')}"

        if payload_id != st.session_state.get("last_processed_payload_id"):
            if action == "audio_recorded":
                st.session_state.last_processed_payload_id = payload_id
                raw_b64 = bot_payload.get("audio_base64", "")

                with st.spinner("⏳ Transcribing patient speech locally..."):
                    audio_bytes = decode_audio_payload(raw_b64)
                    res = transcribe_audio(audio_bytes, language=lang, question_number=current_q_num)

                    if res["success"]:
                        transcript_text = res["transcript"]
                        st.session_state.current_transcript = transcript_text
                        st.session_state[f"manual_text_{current_q_num}"] = transcript_text
                        st.session_state.manual_edit_mode = True
                        st.toast("Review the transcript before saving.", icon="🎙️")

                        if q_type == "rating_and_comment" or current_q_num in (3, 5):
                            extracted, _ = extract_rating(transcript_text, language=lang)
                            st.session_state.current_rating = extracted or 5
                        elif q_type == "boolean_choice" or current_q_num == 4:
                            lower_t = transcript_text.lower()
                            if any(k in lower_t for k in ["हाँ", "yes", "అవును"]):
                                selected_response = "yes"
                            elif any(k in lower_t for k in ["नहीं", "no", "కాదు"]):
                                selected_response = "no"
                            else:
                                selected_response = "yes"
                            st.session_state[f"manual_radio_{current_q_num}"] = selected_response
                    else:
                        st.error(f"⚠️ {res.get('error', 'Transcription failed')}")
                        st.session_state.manual_edit_mode = True

            elif action == "no_speech_detected":
                st.session_state.last_processed_payload_id = payload_id
                st.toast("⚠️ No speech detected. Repeating question...", icon="🔁")
                st.session_state.bot_command = "repeat"
                st.rerun()

            elif action == "mic_error":
                st.session_state.last_processed_payload_id = payload_id
                error_message = bot_payload.get(
                    "error",
                    "Microphone permission denied. Please enable manual entry below."
                )
                st.error(f"⚠️ {error_message}")
                st.session_state.manual_edit_mode = True

    # 3. MANUAL EDIT / FALLBACK REVIEW BOX
    # Allows staff to review, correct, or enter manual answers if microphone or API is restricted
    if st.session_state.get("manual_edit_mode") or st.session_state.get("current_transcript"):
        st.divider()
        st.markdown("### ✏️ Review and Correct the Answer")
        st.caption("Correct any misheard words before saving. Answers are translated to English; only English text is stored.")

        # Rating input if Question 3 or 5
        manual_rating = None
        if current_q_num in (3, 5):
            current_r = st.session_state.get("current_rating") or 5
            manual_rating = st.slider(
                "⭐ Service Rating (1 = Poor, 5 = Excellent):",
                min_value=1,
                max_value=5,
                value=int(current_r),
                key=f"manual_slider_{current_q_num}"
            )

        # Boolean choice if Question 4
        manual_choice = "open_response"
        if current_q_num == 4:
            manual_choice = st.radio(
                "Treatment Explanation Understood?",
                options=["yes", "no", "not_sure"],
                format_func=lambda x: {"yes": "हाँ (Yes)", "no": "नहीं (No)", "not_sure": "निश्चित नहीं (Not sure)"}[x],
                horizontal=True,
                key=f"manual_radio_{current_q_num}"
            )

        manual_text = st.text_area(
            "Recognized answer (Hindi/Telugu):",
            value=st.session_state.get("current_transcript", ""),
            height=90,
            key=f"manual_text_{current_q_num}"
        )

        col_save1, col_save2 = st.columns([2, 1])
        with col_save1:
            if st.button("🌐 Translate & Save English Answer ->", type="primary", width="stretch"):
                resp_text = manual_text.strip()
                if not resp_text and current_q_num == 4:
                    resp_text = manual_choice
                elif not resp_text and current_q_num == 3:
                    resp_text = f"Rating: {manual_rating}/5"
                resp_type = manual_choice if current_q_num == 4 else ("rating" if current_q_num in (3, 5) else "open_response")

                save_result = None
                save_ok = False
                if not resp_text:
                    st.error("Enter the patient's actual answer before saving.")
                else:
                    save_result = _translate_and_save_english_answer(
                        session_id=session_id,
                        question_number=current_q_num,
                        question_text=en_text,
                        answer_text=resp_text,
                        response_type=resp_type,
                        rating=manual_rating,
                        source_language=lang
                    )
                    if save_result["success"]:
                        save_ok = True
                    else:
                        st.error(f"⚠️ English translation/save failed: {save_result['error']}. "
                                 "The answer was not saved; correct it or retry.")

                if save_ok and save_result:
                    eng_trans = save_result["english_translation"]
                    trans_status = save_result["translation_status"]

                    st.session_state.answers_recorded[current_q_num] = {
                        "question": q_text,
                        "transcript": eng_trans,
                        "english_translation": eng_trans,
                        "translation_status": trans_status,
                        "response": resp_type,
                        "rating": manual_rating
                    }

                    st.session_state.current_transcript = ""
                    st.session_state.current_rating = None
                    st.session_state.manual_edit_mode = False

                    if current_q_num >= total_q:
                        complete_feedback_session(session_id)
                        st.session_state.is_completed = True
                    else:
                        st.session_state.current_question_index = current_q_num + 1
                        st.session_state.bot_command = "speak_and_listen"

                    st.rerun()

        with col_save2:
            if st.button("🔁 Re-record Voice", width="stretch"):
                st.session_state.current_transcript = ""
                st.session_state.manual_edit_mode = False
                st.session_state.bot_command = "repeat"
                st.rerun()
