"""Optional Cloudflare Workers AI client for text analysis."""
import os
import json
import requests
from typing import Optional, Dict, Any
from pathlib import Path

# Load environment variables safely with built-in fallback if python-dotenv is missing
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    for candidate in [Path(".env"), Path(__file__).resolve().parent.parent / ".env"]:
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

def _cfg(name: str, default: str = "") -> str:
    """
    Read a setting from the environment first, then from Streamlit secrets
    (`.streamlit/secrets.toml` / Streamlit Community Cloud app secrets).
    Values are never hard-coded.
    """
    val = os.getenv(name, "").strip()
    if val:
        return val
    try:
        import streamlit as st
        val = str(st.secrets[name]).strip()
        if val:
            return val
    except Exception:
        pass
    return default


# Default text model identifier
DEFAULT_TEXT_MODEL = _cfg("CLOUDFLARE_TEXT_MODEL", "@cf/zai-org/glm-4.7-flash")

BASE_URL = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model_id}"

def is_configured() -> bool:
    """
    Check if Cloudflare credentials are configured in environment.
    Returns True only if actual non-placeholder values exist.
    """
    acct = _cfg("CLOUDFLARE_ACCOUNT_ID")
    token = _cfg("CLOUDFLARE_API_TOKEN")
    return bool(
        acct and token and
        acct not in ("your_account_id", "your_cloudflare_account_id") and
        token not in ("your_api_token", "your_cloudflare_api_token")
    )

def parse_cloudflare_error(resp: requests.Response) -> str:
    """
    Parse HTTP status and Cloudflare JSON payload into a friendly, actionable error message.
    Detects quota exhaustion, authentication failure, request errors, and server downtime.
    """
    status_code = resp.status_code
    detail = ""
    try:
        err_json = resp.json()
        errors = err_json.get("errors", [])
        if errors and isinstance(errors, list):
            detail = "; ".join(e.get("message", str(e)) for e in errors)
        elif "messages" in err_json and err_json["messages"]:
            detail = "; ".join(str(m) for m in err_json["messages"])
    except Exception:
        detail = resp.text[:200] if resp.text else ""

    if status_code in (401, 403):
        return f"Authentication Failed (HTTP {status_code}): Invalid or unauthorized Cloudflare credentials. Check CLOUDFLARE_API_TOKEN and ACCOUNT_ID in .env. ({detail})"
    elif status_code == 429:
        return f"Cloudflare Free-Tier Limit / Rate Limit Hit (HTTP 429): Daily free neurons allocation or request rate reached. Please use manual text fallback. ({detail})"
    elif status_code in (400, 415):
        return f"Cloudflare rejected the text analysis request (HTTP {status_code}): {detail}"
    elif status_code >= 500:
        return f"Cloudflare Service Temporarily Unavailable (HTTP {status_code}): Upstream AI inference error. Your answer is safe; please retry or type manually. ({detail})"
    else:
        return f"Cloudflare API Error (HTTP {status_code}): {detail or resp.reason}"

def run_text_model(prompt: str, system_prompt: Optional[str] = None, model_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Optional text intelligence via Cloudflare Workers AI free allocation.
    Supports chat completion schema (choices[0].message.content).
    Returns:
      {
        "success": bool,
        "response": str,
        "error": Optional[str],
        "status_code": Optional[int]
      }
    """
    if not is_configured():
        return {
            "success": False,
            "response": "",
            "error": "Cloudflare credentials not configured.",
            "status_code": None
        }

    acct = _cfg("CLOUDFLARE_ACCOUNT_ID")
    token = _cfg("CLOUDFLARE_API_TOKEN")
    model = model_id or DEFAULT_TEXT_MODEL
    url = BASE_URL.format(account_id=acct, model_id=model)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "messages": messages,
        "max_tokens": 1024,
        "temperature": 0.2
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=35)
        if resp.status_code == 200:
            data = resp.json()
            if not data.get("success", True):
                err_msg = parse_cloudflare_error(resp)
                return {
                    "success": False,
                    "response": "",
                    "error": err_msg,
                    "status_code": 200
                }

            result = data.get("result", {})
            response_text = ""

            # Extract content from choices
            if isinstance(result, dict):
                choices = result.get("choices", [])
                if choices and isinstance(choices, list):
                    first_choice = choices[0]
                    if isinstance(first_choice, dict):
                        msg = first_choice.get("message", {})
                        if isinstance(msg, dict):
                            response_text = msg.get("content") or ""
                            if not response_text:
                                response_text = msg.get("reasoning") or ""
                        if not response_text:
                            response_text = first_choice.get("text") or ""

                if not response_text:
                    response_text = result.get("response") or result.get("text") or ""
            elif isinstance(result, str):
                response_text = result

            clean_text = (response_text or "").strip()
            if not clean_text:
                return {
                    "success": False,
                    "response": "",
                    "error": "Cloudflare Text AI returned an empty response.",
                    "status_code": 200
                }

            return {
                "success": True,
                "response": clean_text,
                "error": None,
                "status_code": 200
            }
        else:
            err_msg = parse_cloudflare_error(resp)
            return {
                "success": False,
                "response": "",
                "error": err_msg,
                "status_code": resp.status_code
            }
    except Exception as e:
        return {
            "success": False,
            "response": "",
            "error": str(e),
            "status_code": None
        }
