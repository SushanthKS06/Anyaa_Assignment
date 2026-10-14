"""LLM wrapper: llm.chat(messages, tools, role) with fallback chain + logging.

Chain: Gemini 2.5 Flash -> Groq llama-3.3-70b-versatile -> deterministic mock.
Zero keys => mock. Forced-429 test hook => raises through tenacity then falls back.
No invented SDK calls: provider SDKs imported lazily inside try/except; REST not
called unless keys + explicit non-mock mode. Verified 2026-10-14:
  - pip package `google-genai` (import google.genai) exists, latest 1.x
  - pip package `groq` (import groq) exists
If either import fails at runtime we fall back to mock and log why.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import CONFIG
from app.logging_setup import jsonl_append


class RateLimitError(RuntimeError):
    pass


class ProviderError(RuntimeError):
    pass


_CACHE: dict[str, str] = {}


def _cache_key(messages: list[dict[str, str]], role: str) -> str:
    h = hashlib.sha256()
    h.update(role.encode())
    for m in messages:
        h.update(m.get("role", "").encode())
        h.update(b"\x00")
        h.update(m.get("content", "").encode())
        h.update(b"\x00")
    return h.hexdigest()[:32]


_GROQ_FALLBACK_MODELS = ("qwen/qwen3.8-27b", "openai/gpt-oss-120b")
_gemini_cooldown_until: float = 0.0


def clear_cache() -> None:
    _CACHE.clear()


def _mock_reply(messages: list[dict[str, str]], role: str) -> str:
    last = messages[-1]["content"] if messages else ""
    # If this was a polish prompt ("Say this warmly in...: <text>"), return the inner text directly
    if ": " in last and any(p in last for p in ["Say this", "warmly in"]):
        candidate = last.split(": ", 1)[-1].strip()
        if candidate:
            return candidate
    low = last.lower()
    if any(g in low for g in ["வணக்கம்", "namaste", "hello", "hi", "hey", "vanakkam"]):
        return "Namaste! Main Rasoi — tumhare ghar ka khana sambhalungi. Ghar me kaun kaun hai?"
    if role == "cook":
        return "Theek hai. Kal ka plan simple rakhenge. Quantity repeat karke confirm karenge."
    return "Samajh gaya. Agla ek sawal — kaun kaun khayega aur kitne din ka plan banau?"


def _try_gemini(messages: list[dict[str, str]], force_429: bool) -> str:
    if force_429:
        raise RateLimitError("forced 429 for smoke test")
    if not CONFIG.gemini_api_key:
        raise ProviderError("no GEMINI_API_KEY")
    try:
        from google import genai  # type: ignore
    except Exception as e:
        raise ProviderError(f"google-genai import failed: {e}") from e
    client = genai.Client(api_key=CONFIG.gemini_api_key)
    prompt = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    try:
        resp = client.models.generate_content(model=CONFIG.gemini_model, contents=prompt)
        text = getattr(resp, "text", "") or ""
    except Exception as e:
        msg = str(e)
        if "429" in msg or "rate" in msg.lower() or "quota" in msg.lower() or "exhausted" in msg.lower():
            raise RateLimitError(msg) from e
        raise ProviderError(msg) from e
    if not text.strip():
        raise ProviderError("empty gemini response")
    return text


def _try_groq(messages: list[dict[str, str]], force_429: bool) -> tuple[str, str]:
    if force_429:
        raise RateLimitError("forced 429 for smoke test")
    if not CONFIG.groq_api_key:
        raise ProviderError("no GROQ_API_KEY")
    try:
        from groq import Groq  # type: ignore
    except Exception as e:
        raise ProviderError(f"groq import failed: {e}") from e
    client = Groq(api_key=CONFIG.groq_api_key)

    candidates = [CONFIG.groq_model] + [m for m in _GROQ_FALLBACK_MODELS if m != CONFIG.groq_model]
    last_err: Exception | None = None
    for model_name in candidates:
        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=[{"role": m["role"], "content": m["content"]} for m in messages],  # type: ignore
                max_tokens=CONFIG.groq_max_tokens,
                temperature=0.6,
            )
            text = (resp.choices[0].message.content or "").strip()
            if text:
                return text, model_name
        except Exception as e:
            msg = str(e)
            if "429" in msg or "rate" in msg.lower():
                raise RateLimitError(msg) from e
            last_err = e
            continue

    if last_err:
        raise ProviderError(str(last_err)) from last_err
    raise ProviderError("empty groq response")


@retry(
    retry=retry_if_exception_type((RateLimitError, ProviderError)),
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.2, max=1.0),
    reraise=True,
)
def _primary_with_retry(messages: list[dict[str, str]], force_429: bool) -> tuple[str, str]:
    global _gemini_cooldown_until
    if force_429:
        raise RateLimitError("forced 429 for smoke test")

    now = time.time()
    if now < _gemini_cooldown_until and CONFIG.groq_api_key:
        text, g_model = _try_groq(messages, force_429)
        return text, f"groq:{g_model}"

    try:
        return _try_gemini(messages, force_429), f"gemini:{CONFIG.gemini_model}"
    except RateLimitError as e_rate:
        _gemini_cooldown_until = time.time() + 600.0
        try:
            text, g_model = _try_groq(messages, force_429)
            return text, f"groq:{g_model}"
        except Exception:
            raise e_rate
    except ProviderError as e_gem:
        try:
            text, g_model = _try_groq(messages, force_429)
            return text, f"groq:{g_model}"
        except Exception:
            raise e_gem


def chat(
    messages: list[dict[str, str]],
    tools: list[dict[str, Any]] | None = None,
    role: str = "household",
    force_429: bool = False,
    use_mock: bool | None = None,
) -> dict[str, Any]:
    """Main entry. Returns dict(text, model, latency_ms, cached, fallback)."""
    _ = tools  # tool-calling wired in M3; accepted for API stability
    key = _cache_key(messages, role)
    if key in _CACHE:
        return {"text": _CACHE[key], "model": "cache", "latency_ms": 0.0, "cached": True, "fallback": None}
    t0 = time.perf_counter()
    mock = CONFIG.mock_default if use_mock is None else use_mock
    if mock or (not CONFIG.gemini_api_key and not CONFIG.groq_api_key):
        text = _mock_reply(messages, role)
        model, fallback = "mock:deterministic", "no-keys" if not mock else "mock-requested"
    else:
        try:
            text, model = _primary_with_retry(messages, force_429)
            fallback = None
        except Exception as e:
            text = _mock_reply(messages, role)
            model, fallback = "mock:deterministic", f"providers-failed:{type(e).__name__}"
    latency_ms = (time.perf_counter() - t0) * 1000
    _CACHE[key] = text
    jsonl_append(
        CONFIG.log_dir,
        "llm.jsonl",
        {"model": model, "role": role, "latency_ms": round(latency_ms, 1),
         "fallback": fallback, "prompt_chars": sum(len(m.get("content", "")) for m in messages)},
    )
    return {"text": text, "model": model, "latency_ms": latency_ms, "cached": False, "fallback": fallback}
