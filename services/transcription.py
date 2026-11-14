"""Audio validation and local CPU speech transcription."""
import io
import logging
from typing import Any, Dict, Union

from .local_transcription import transcribe_local_audio

logger = logging.getLogger(__name__)


def transcribe_audio(
    audio_input: Union[bytes, io.BytesIO, Any],
    language: str = "hi",
    question_number: int = 1,
) -> Dict[str, Any]:
    """Transcribe browser-recorded audio locally without persisting the audio."""
    if audio_input is None:
        return {
            "success": False,
            "transcript": "",
            "error": "No audio data received. Please record your voice or type text.",
            "is_mock": False,
            "mode": "local",
        }

    try:
        if isinstance(audio_input, bytes):
            audio_bytes = audio_input
        elif hasattr(audio_input, "read"):
            audio_input.seek(0)
            audio_bytes = audio_input.read()
        elif hasattr(audio_input, "getvalue"):
            audio_bytes = audio_input.getvalue()
        else:
            return {
                "success": False,
                "transcript": "",
                "error": "Unsupported audio input. Please record again or enter text.",
                "is_mock": False,
                "mode": "local",
            }
    except Exception as exc:
        return {
            "success": False,
            "transcript": "",
            "error": f"Failed to read audio data: {exc}",
            "is_mock": False,
            "mode": "local",
        }

    if len(audio_bytes) < 200:
        return {
            "success": False,
            "transcript": "",
            "error": "Audio recording is empty or too short. Please record again or enter text.",
            "is_mock": False,
            "mode": "local",
        }

    try:
        transcript = transcribe_local_audio(audio_bytes, language)
    except Exception as exc:
        logger.exception("Local Whisper transcription failed")
        return {
            "success": False,
            "transcript": "",
            "error": f"Local transcription failed: {exc}",
            "is_mock": False,
            "mode": "local",
        }

    if not transcript:
        return {
            "success": False,
            "transcript": "",
            "error": "No speech was recognized. Please record again or enter the answer manually.",
            "is_mock": False,
            "mode": "local",
        }

    return {
        "success": True,
        "transcript": transcript,
        "error": None,
        "is_mock": False,
        "mode": "local",
    }
