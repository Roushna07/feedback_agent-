"""
Voice Bot Streamlit Component Wrapper.
Bridges browser-based SpeechSynthesis, MediaRecorder, and Web Audio API silence detection with Python.
"""
import os
import base64
import streamlit as st
import streamlit.components.v1 as components
from typing import Optional, Dict, Any

# Locate component folder
_COMPONENT_PATH = os.path.join(os.path.dirname(__file__), "voice_bot_component")
_voice_bot_func = components.declare_component("voice_bot_component", path=_COMPONENT_PATH)

def render_voice_bot(
    question_number: int,
    question_text: str,
    language: str = "hi",
    is_bot_active: bool = False,
    command: str = "idle",
    key: Optional[str] = "voice_bot_widget"
) -> Optional[Dict[str, Any]]:
    """
    Renders the browser voice bot component.
    Returns dictionary delivered by JavaScript upon audio recording, silence detection, or errors:
      {
        "action": "audio_recorded" | "no_speech_detected" | "mic_error",
        "audio_base64": str,
        "question_number": int,
        "duration": float,
        "reason": str
      }
    """
    return _voice_bot_func(
        question_number=question_number,
        question_text=question_text,
        language=language,
        is_bot_active=is_bot_active,
        command=command,
        key=key,
        default=None
    )

def decode_audio_payload(b64_string: str) -> bytes:
    """Safely decode base64 audio payload from browser."""
    if not b64_string:
        return b""
    # Strip data URL header if present
    if "," in b64_string:
        b64_string = b64_string.split(",", 1)[1]
    return base64.b64decode(b64_string)
