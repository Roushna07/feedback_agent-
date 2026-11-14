"""
Speech-to-Text service module.
Coordinates audio validation and transcription via Cloudflare Workers AI Whisper model.
Strictly separates Preview Mode and Live Mode to ensure authentic transcription and transparent evaluation.
"""
from typing import Dict, Any, Union, Optional
import io
from .cloudflare_ai import run_stt_model, is_configured

# Explicit simulated samples for Preview Mode corresponding to the 5 camp questions
PREVIEW_SAMPLES = {
    "hi": [
        "मेरा नाम रमेश कुमार है और मैं रामपुर गाँव से आया हूँ।",
        "मुझे पिछले तीन दिनों से बुखार, सर्दी और जोड़ों में दर्द है।",
        "स्वास्थ्य सहायक ने बहुत अच्छे से जाँच की और सम्मानपूर्वक बात की।",
        "हाँ, स्वास्थ्यकर्मी ने सभी दवाइयाँ और समय पर लेने का तरीका अच्छी तरह समझाया।",
        "कैंप में दवाइयों की मात्रा बढ़ाई जाए और ऐसे शिविर हर महीने लगाए जाने चाहिए।"
    ],
    "te": [
        "నా పేరు రమేష్ రావు, మాది కొత్తూరు గ్రామం.",
        "నాకు గత మూడు రోజులుగా తీవ్రమైన జ్వరం మరియు కీళ్ల నొప్పులు ఉన్నాయి.",
        "హెల్త్ అసిస్టెంట్ చాలా బాగా పరీక్షించారు మరియు మంచి సేవ అందించారు.",
        "అవును, సిబ్బంది చికిత్స విధానం మరియు మందుల గురించి స్పష్టంగా వివరించారు.",
        "క్యాంపులో మందులు ఎక్కువగా అందుబాటులో ఉంచాలి మరియు ప్రతి నెలా క్యాంప్ నిర్వహించాలి."
    ]
}

def transcribe_audio(
    audio_input: Union[bytes, io.BytesIO, Any],
    language: str = "hi",
    question_number: int = 1
) -> Dict[str, Any]:
    """
    Transcribe recorded patient audio.

    Modes:
    1. Preview Mode (Credentials NOT set):
       Generates an explicitly labeled simulated transcription for UI & database workflow testing.
       Must NEVER be mistaken for real speech recognition.
    2. Live Mode (Credentials set):
       Dispatches real audio bytes to Cloudflare Workers AI Whisper Large V3 Turbo.
       On any failure (quota/network/auth), NEVER fabricates text; returns explicit error and triggers manual text fallback.
    """
    if audio_input is None:
        return {
            "success": False,
            "transcript": "",
            "error": "No audio data received. Please record your voice or type text.",
            "is_mock": False,
            "mode": "live" if is_configured() else "preview"
        }

    # Extract audio bytes safely
    audio_bytes = b""
    try:
        if isinstance(audio_input, bytes):
            audio_bytes = audio_input
        elif hasattr(audio_input, "read"):
            audio_input.seek(0)
            audio_bytes = audio_input.read()
        elif hasattr(audio_input, "getvalue"):
            audio_bytes = audio_input.getvalue()
    except Exception as e:
        return {
            "success": False,
            "transcript": "",
            "error": f"Failed to read audio data: {str(e)}",
            "is_mock": False,
            "mode": "live" if is_configured() else "preview"
        }

    # Minimum size validation (valid audio header + frames requires > 200 bytes)
    if len(audio_bytes) < 200:
        return {
            "success": False,
            "transcript": "",
            "error": "Audio recording is empty or too short. Please speak clearly into the microphone.",
            "is_mock": False,
            "mode": "live" if is_configured() else "preview"
        }

    # 1. PREVIEW MODE (Credentials absent or placeholder)
    if not is_configured():
        sample_idx = min(max(question_number - 1, 0), 4)
        sample_pool = PREVIEW_SAMPLES.get(language, PREVIEW_SAMPLES["hi"])
        sample_text = sample_pool[sample_idx]

        prefix = "[సిమ్యులేటెడ్ ప్రివ్యూ / PREVIEW]" if language == "te" else "[पूर्वावलोकन / PREVIEW]"

        return {
            "success": True,
            "transcript": f"{prefix}: {sample_text}",
            "error": "PREVIEW MODE: Cloudflare API credentials not configured. Showing clearly labeled simulated response.",
            "is_mock": True,
            "mode": "preview"
        }

    # 2. LIVE PRODUCTION MODE (Live Cloudflare Workers AI Call)
    # Strictly genuine transcription - never fabricate text on failure
    res = run_stt_model(audio_bytes, language=language)

    if res["success"]:
        return {
            "success": True,
            "transcript": res["text"],
            "error": None,
            "is_mock": False,
            "mode": "live",
            "status_code": res.get("status_code", 200)
        }
    else:
        # Failure in live mode: Never fabricate
        return {
            "success": False,
            "transcript": "",
            "error": res["error"],
            "is_mock": False,
            "mode": "live",
            "status_code": res.get("status_code")
        }
