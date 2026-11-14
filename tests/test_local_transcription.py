import io
import wave

from services import local_transcription, transcription


def _sample_wav(sample_rate: int = 16000, frames: int = 1600) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(b"\x00\x00" * frames)
    return output.getvalue()


def test_transcription_runs_through_local_whisper(monkeypatch):
    seen = {}

    class FakeSegment:
        text = "  Patient response  "

    class FakeModel:
        def transcribe(self, audio, **options):
            seen["audio"] = audio.copy()
            seen["options"] = options
            return iter([FakeSegment()]), object()

    monkeypatch.setattr(local_transcription, "_MODEL", FakeModel())
    result = transcription.transcribe_audio(_sample_wav(), language="hi")

    assert result == {
        "success": True,
        "transcript": "Patient response",
        "error": None,
        "is_mock": False,
        "mode": "local",
    }
    assert seen["audio"].shape == (1600,)
    assert seen["audio"].dtype.name == "float32"
    assert not seen["audio"].any()
    assert seen["options"]["language"] == "hi"


def test_transcription_resamples_audio_in_memory(monkeypatch):
    seen = {}

    class FakeModel:
        def transcribe(self, audio, **options):
            seen["audio"] = audio.copy()
            return iter([type("Segment", (), {"text": "Response"})()]), object()

    monkeypatch.setattr(local_transcription, "_MODEL", FakeModel())
    result = transcription.transcribe_audio(
        _sample_wav(sample_rate=22050, frames=2205),
        language="en",
    )

    assert result["success"] is True
    assert seen["audio"].shape == (1600,)
    assert seen["audio"].dtype.name == "float32"


def test_transcription_rejects_empty_audio_without_loading_model():
    result = transcription.transcribe_audio(b"", language="te")

    assert result["success"] is False
    assert result["mode"] == "local"
    assert "too short" in result["error"]
