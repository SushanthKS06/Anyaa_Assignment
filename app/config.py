"""Central config. Env-driven, zero-key safe. M0.

Every tunable value lives here and is read from environment variables so that
nothing is hardcoded in downstream modules. Sensible defaults are kept as
fallbacks so the system runs offline with zero configuration.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int(name: str, default: int) -> int:
    v = os.environ.get(name)
    if v is None:
        return default
    try:
        return int(v.strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    # LLM: primary -> fallback chain
    gemini_api_key: str = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"))
    groq_api_key: str = field(default_factory=lambda: os.environ.get("GROQ_API_KEY", ""))
    groq_model: str = field(default_factory=lambda: os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"))
    groq_max_tokens: int = field(default_factory=lambda: _int("GROQ_MAX_TOKENS", 2048))

    # Sarvam STT/TTS - key-gated; all URLs/models are env-overridable
    sarvam_api_key: str = field(default_factory=lambda: os.environ.get("SARVAM_API_KEY", ""))
    sarvam_stt_url: str = field(default_factory=lambda: os.environ.get("SARVAM_STT_URL", "https://api.sarvam.ai/speech-to-text"))
    sarvam_stt_model: str = field(default_factory=lambda: os.environ.get("SARVAM_STT_MODEL", "saaras:v3"))
    sarvam_stt_language: str = field(default_factory=lambda: os.environ.get("SARVAM_STT_LANGUAGE", "hi-IN"))
    sarvam_tts_url: str = field(default_factory=lambda: os.environ.get("SARVAM_TTS_URL", "https://api.sarvam.ai/text-to-speech"))
    sarvam_tts_model: str = field(default_factory=lambda: os.environ.get("SARVAM_TTS_MODEL", "bulbul:v3"))
    sarvam_tts_speaker: str = field(default_factory=lambda: os.environ.get("SARVAM_TTS_SPEAKER", "priya"))
    sarvam_tts_language: str = field(default_factory=lambda: os.environ.get("SARVAM_TTS_LANGUAGE", "hi-IN"))

    # Feature flags
    voice_enabled: bool = field(default_factory=lambda: _bool("VOICE_ENABLED", False))
    mock_default: bool = field(default_factory=lambda: _bool("LLM_MOCK_DEFAULT", True))

    # Voice first-chunk latency budget (ms). Default adapts: 2000ms for mock, 10000ms for remote LLMs
    voice_latency_budget_ms: int = field(
        default_factory=lambda: _int(
            "VOICE_LATENCY_BUDGET_MS",
            2000 if _bool("LLM_MOCK_DEFAULT", True) else 10000,
        )
    )

    # Paths
    log_dir: str = field(default_factory=lambda: os.environ.get("LOG_DIR", "logs"))
    db_path: str = field(default_factory=lambda: os.environ.get("DB_PATH", "data/app.db"))

    # Planner / grocery reproducibility. Set to -1 for a random seed each run.
    planner_seed: int = field(default_factory=lambda: _int("PLANNER_SEED", 42))
    grocery_seed: int = field(default_factory=lambda: _int("GROCERY_SEED", 42))


CONFIG = Config()
