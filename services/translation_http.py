"""
Optional remote translation adapter.

Used ONLY when TRANSLATION_BACKEND=http. It lets the ~600 MB NLLB model run
on a separate free CPU service (for example a second free container or a
self-hosted instance of this repository's `api.py` exposing `/api/translate`)
while the Streamlit app stays within its memory budget.

- No paid APIs are introduced: the endpoint must be your own deployment.
- The original transcript is never modified; failures are reported with
  translation_status="failed" so the UI can retry later.
"""
import os
import time
from typing import Any, Dict

import requests

MODEL_IDENTIFIER = "nllb-200-distilled-600M-ctranslate2-int8-remote"


def _failed(error: str, started: float) -> Dict[str, Any]:
    return {
        "success": False,
        "english_translation": "",
        "translation_status": "failed",
        "translation_engine": MODEL_IDENTIFIER,
        "latency_ms": round((time.time() - started) * 1000, 1),
        "error": error,
    }


def translate_via_http(transcript: str, source_language: str,
                       timeout: int = 30) -> Dict[str, Any]:
    """
    Translate via a remote endpoint. The endpoint must return either the
    full result dictionary of `translate_patient_transcript`:
        {"success", "english_translation", "translation_status", ...}
    or the legacy shape used by `api.py /api/translate`:
        {"translated_text", "engine"}
    """
    started = time.time()
    url = os.getenv("TRANSLATION_HTTP_URL", "").strip()
    if not url:
        return _failed(
            "TRANSLATION_BACKEND=http but TRANSLATION_HTTP_URL is not set. "
            "Point it at your own free translation service.", started)

    try:
        resp = requests.post(
            url,
            json={"text": transcript, "source_language": source_language},
            timeout=timeout,
        )
    except requests.exceptions.Timeout:
        return _failed(f"Remote translation timed out ({timeout}s).", started)
    except requests.RequestException as exc:
        return _failed(f"Remote translation unreachable: {exc}", started)

    if resp.status_code != 200:
        return _failed(f"Remote translation returned HTTP {resp.status_code}.", started)

    try:
        data = resp.json()
    except ValueError:
        return _failed("Remote translation returned invalid JSON.", started)

    # Shape 1: full result dictionary
    if isinstance(data, dict) and "english_translation" in data:
        return {
            "success": bool(data.get("success")),
            "english_translation": data.get("english_translation") or "",
            "translation_status": data.get("translation_status", "failed"),
            "translation_engine": data.get("translation_engine", MODEL_IDENTIFIER),
            "latency_ms": round((time.time() - started) * 1000, 1),
            "error": data.get("error"),
        }

    # Shape 2: legacy api.py /api/translate response
    if isinstance(data, dict) and "translated_text" in data:
        text = (data.get("translated_text") or "").strip()
        if text and text != transcript.strip():
            return {
                "success": True,
                "english_translation": text,
                "translation_status": "translated",
                "translation_engine": data.get("engine", MODEL_IDENTIFIER),
                "latency_ms": round((time.time() - started) * 1000, 1),
                "error": None,
            }
        return _failed("Remote translation returned unchanged text.", started)

    return _failed("Unexpected remote translation response shape.", started)
