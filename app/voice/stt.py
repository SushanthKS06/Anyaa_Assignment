"""STT: Sarvam Saaras per-utterance REST when SARVAM_API_KEY exists, else mock.
All URLs, model names, and language codes come from CONFIG (env-driven).
Cockpit uses browser WebSpeech until a key is set."""
from __future__ import annotations

import httpx

from app.config import CONFIG


def mock_stt(transcript: str) -> dict[str, str]:
    return {"text": transcript.strip(), "engine": "mock:deterministic", "simulated": "true"}  # type: ignore


import base64


def sarvam_stt(audio_b64: str, language_code: str | None = None) -> dict:
    """REAL path, key-gated. Raises RuntimeError without key; network errors propagate."""
    if not CONFIG.sarvam_api_key:
        raise RuntimeError("no SARVAM_API_KEY -- browser WebSpeech or mock only")
    if "," in audio_b64:
        audio_b64 = audio_b64.split(",", 1)[1]
    audio_bytes = base64.b64decode(audio_b64)
    lang = language_code or CONFIG.sarvam_stt_language
    r = httpx.post(
        CONFIG.sarvam_stt_url,
        headers={"api-subscription-key": CONFIG.sarvam_api_key},
        files={"file": ("audio.wav", audio_bytes, "audio/wav")},
        data={
            "language_code": lang,
            "model": CONFIG.sarvam_stt_model,
        },
        timeout=25,
    )
    r.raise_for_status()
    data = r.json()
    return {"text": data.get("transcript", ""), "engine": f"sarvam:{CONFIG.sarvam_stt_model}", "lang": lang, "simulated": False}


def transcribe(audio_b64: str | None = None, transcript: str = "", language_code: str | None = None) -> dict:
    if audio_b64 and CONFIG.sarvam_api_key:
        try:
            return sarvam_stt(audio_b64, language_code=language_code)
        except Exception:
            pass  # fall through to echo/mock
    return mock_stt(transcript)
