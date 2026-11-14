"""
Session state manager for Streamlit patient conversation flow.
Updated for Automated Multilingual Voice Interview Bot state machine:
States:
- IDLE
- SPEAKING_QUESTION
- LISTENING
- TRANSCRIBING
- REVIEWING
- SAVING
- NEXT_QUESTION
- PAUSED
- COMPLETED
- ERROR
"""
import streamlit as st
from typing import Optional, Dict, Any
from database.repository import create_feedback_session, complete_feedback_session, generate_patient_code

def init_agent_state():
    """Ensure all required session state variables exist."""
    defaults = {
        "session_id": None,
        "patient_code": None,
        "language": "hi",  # default Hindi
        "consent_given": False,
        "current_question_index": 1,
        "current_transcript": "",
        "current_response_type": "open_response",
        "current_rating": None,
        "answers_recorded": {},
        "is_completed": False,
        "error_message": None,
        "info_message": None,
        # Automated Voice Bot States
        "bot_active": False,
        "bot_state": "IDLE",  # IDLE, SPEAKING_QUESTION, LISTENING, TRANSCRIBING, REVIEWING, SAVING, PAUSED, COMPLETED, ERROR
        "bot_command": "idle", # speak_and_listen, pause, resume, repeat, stop, idle
        "last_processed_payload_id": None,
        "auto_advance": True,
        "manual_edit_mode": False
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

def start_new_session(language: str = "hi"):
    """Initialize or reset state for a new patient feedback interaction."""
    patient_code = generate_patient_code()
    session_id = create_feedback_session(language=language, patient_code=patient_code, consent_given=True)

    st.session_state.session_id = session_id
    st.session_state.patient_code = patient_code
    st.session_state.language = language
    st.session_state.consent_given = True
    st.session_state.current_question_index = 1
    st.session_state.current_transcript = ""
    st.session_state.current_response_type = "open_response"
    st.session_state.current_rating = None
    st.session_state.answers_recorded = {}
    st.session_state.is_completed = False
    st.session_state.error_message = None
    st.session_state.info_message = None
    st.session_state.bot_active = True
    st.session_state.bot_state = "SPEAKING_QUESTION"
    st.session_state.bot_command = "speak_and_listen"
    st.session_state.last_processed_payload_id = None
    st.session_state.manual_edit_mode = False

def reset_session_state():
    """Clear session back to welcome / language selection screen."""
    st.session_state.session_id = None
    st.session_state.patient_code = None
    st.session_state.consent_given = False
    st.session_state.current_question_index = 1
    st.session_state.current_transcript = ""
    st.session_state.current_rating = None
    st.session_state.answers_recorded = {}
    st.session_state.is_completed = False
    st.session_state.error_message = None
    st.session_state.info_message = None
    st.session_state.bot_active = False
    st.session_state.bot_state = "IDLE"
    st.session_state.bot_command = "idle"
    st.session_state.last_processed_payload_id = None
    st.session_state.manual_edit_mode = False
