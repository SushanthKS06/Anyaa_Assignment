"""TTS: Sarvam Bulbul per-sentence REST when key exists, else browser TTS.
All URLs, model names, speaker, and language codes come from CONFIG (env-driven).
Server returns {engine, audio_b64?, text}; cockpit speaks via speechSynthesis
when engine == 'browser'. Fixed-line phrase cache avoids repeat synthesis."""
from __future__ import annotations

import httpx

from app.config import CONFIG

_PHRASE_CACHE: dict[str, dict] = {}


def mock_tts(text: str) -> dict:
    return {"engine": "browser", "text": text, "simulated": True,
            "note": "browser speechSynthesis (no Sarvam key)"}


def sarvam_tts(text: str, language_code: str | None = None) -> dict:
    if not CONFIG.sarvam_api_key:
        raise RuntimeError("no SARVAM_API_KEY -- browser TTS only")
    lang = language_code or CONFIG.sarvam_tts_language
    cache_key = f"{lang}:{text}"
    if cache_key in _PHRASE_CACHE:
        return {**_PHRASE_CACHE[cache_key], "cached": True}
    # Sarvam v3 expects {"inputs": [text], ...}
    r = httpx.post(
        CONFIG.sarvam_tts_url,
        headers={"api-subscription-key": CONFIG.sarvam_api_key},
        json={
            "inputs": [text],
            "target_language_code": lang,
            "model": CONFIG.sarvam_tts_model,
            "speaker": CONFIG.sarvam_tts_speaker,
        },
        timeout=25,
    )
    r.raise_for_status()
    data = r.json()
    audios = data.get("audios") or [data.get("audio", "")]
    audio_b64 = audios[0] if audios else ""
    out = {
        "engine": f"sarvam:{CONFIG.sarvam_tts_model}",
        "audio_b64": audio_b64,
        "text": text,
        "lang": lang,
        "simulated": False,
    }
    if len(_PHRASE_CACHE) < 200:
        _PHRASE_CACHE[cache_key] = out
    return out


def synth(text: str, language_code: str | None = None) -> dict:
    if CONFIG.sarvam_api_key:
        try:
            return sarvam_tts(text, language_code=language_code)
        except Exception:
            pass  # fall back to browser TTS
    return mock_tts(text)
