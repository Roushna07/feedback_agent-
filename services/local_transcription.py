"""On-device speech transcription using Faster-Whisper on the CPU."""
import io
import os
import threading
import wave

import numpy as np

_MODEL = None
_MODEL_LOCK = threading.Lock()


def get_local_stt_model_name() -> str:
    """Return the configured multilingual Whisper model name."""
    return os.getenv("LOCAL_STT_MODEL", "base").strip() or "base"


def _get_model():
    global _MODEL
    with _MODEL_LOCK:
        if _MODEL is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise RuntimeError(
                    "Local transcription requires faster-whisper. "
                    "Install dependencies with `pip install -r requirements.txt`."
                ) from exc

            _MODEL = WhisperModel(
                get_local_stt_model_name(),
                device="cpu",
                compute_type="int8",
            )
    return _MODEL


def transcribe_local_audio(audio_bytes: bytes, language: str) -> str:
    """Transcribe audio in memory; raw audio is not written to disk or uploaded."""
    if language not in {"hi", "te", "en"}:
        raise ValueError(f"Unsupported transcription language: {language!r}.")

    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as audio_file:
            if (
                audio_file.getnchannels() != 1
                or audio_file.getsampwidth() != 2
                or audio_file.getcomptype() != "NONE"
            ):
                raise ValueError("Audio must be uncompressed 16-bit mono WAV.")
            sample_rate = audio_file.getframerate()
            samples = np.frombuffer(audio_file.readframes(audio_file.getnframes()), dtype="<i2")
    except (wave.Error, EOFError) as exc:
        raise ValueError("Audio must be a valid uncompressed WAV recording.") from exc

    audio = samples.astype(np.float32) / 32768.0
    if sample_rate != 16000 and audio.size:
        target_length = round(audio.size * 16000 / sample_rate)
        source_positions = np.arange(audio.size)
        target_positions = np.arange(target_length) * sample_rate / 16000
        audio = np.interp(target_positions, source_positions, audio).astype(np.float32)
    model = _get_model()
    segments, _ = model.transcribe(
        audio,
        language=language,
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    return " ".join(segment.text.strip() for segment in segments).strip()
