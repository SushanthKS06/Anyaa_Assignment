"""M5 voice/cockpit tests: WS protocol, text parity, barge-in, latency, TTS fallback."""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from fastapi.testclient import TestClient  # noqa: E402

from app.config import CONFIG  # noqa: E402
from app.agent.orchestrator import OrchestratorState  # noqa: E402
from app.main import app  # noqa: E402
from app.voice.session import VoiceSession, split_sentences  # noqa: E402
from app.voice.stt import mock_stt, transcribe  # noqa: E402
from app.voice.tts import mock_tts, synth  # noqa: E402

client = TestClient(app)

TURNS = ["Namaste",
         "Ghar me 2 log hain — Dadi Jain hain, Papa diabetic hain",
         "5 din ka plan banao, budget 4000 ka hai"]


def _drain_turn(ws, text, voice=False):
    ws.send_json({"type": "user_text", "text": text, "voice": voice})
    evs = []
    while True:
        m = ws.receive_json()
        evs.append(m)
        if m["type"] == "state":
            break
    return evs


def test_health_and_info() -> None:
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["milestone"] == "M5"
    assert client.get("/api/info").json()["simulated"]


def test_ws_text_turns_and_state() -> None:
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "ready"
        budget = CONFIG.voice_latency_budget_ms
        for t in TURNS:
            evs = _drain_turn(ws, t)
            kinds = [e["type"] for e in evs]
            assert kinds == ["assistant", "tools", "state"], kinds
            assert evs[0]["latency_ms"] < budget, f"server first-chunk budget ({budget}ms)"
        st = evs[-1]["state"]
        assert len(st["members"]) == 2 and len(st["plan"]) == 5


def test_text_parity_cli_vs_voice_session() -> None:
    import asyncio
    async def run(v: VoiceSession):
        out = []
        for t in TURNS:
            async for ev in v.turn(t, voice=False):
                if ev["type"] == "assistant":
                    out.append(ev["text"])
        return out
    via_ws = asyncio.run(run(VoiceSession(hid="hh-parity-a")))
    cli = OrchestratorState(hid="hh-parity-b")
    direct = [cli.handle_user(t) for t in TURNS]
    assert via_ws == direct, "voice path must equal text core"


def test_barge_in_interrupt_truncates() -> None:
    import asyncio
    async def go():
        v = VoiceSession(hid="hh-barge")
        for t in TURNS:
            async for _ in v.turn(t, voice=False):
                pass
        v.reset_interrupt()
        gen = v.turn("aaj ka brief batao", voice=True)
        seen, truncated = [], 0
        async for ev in gen:  # manual iteration so we can interrupt mid-stream
            seen.append(ev["type"])
            if ev["type"] == "tts":
                r = v.interrupt(spoken_chars=10)
                truncated = r["truncated_to"]
                break
        rest = [ev["type"] async for ev in gen]
        hist = [e for e in v.st.transcript if e["role"] == "assistant"][-1]["text"]
        return seen, rest, truncated, hist
    seen, rest, truncated, hist = asyncio.run(go())
    assert "assistant" in seen and "tts" in seen
    assert rest == [], "no more sentences after interrupt"
    assert truncated > 0 and hist.endswith("…[interrupted]")


def test_tts_stt_fallback_no_key() -> None:
    assert mock_tts("hello")["engine"] == "browser"
    orig = CONFIG.sarvam_api_key
    try:
        object.__setattr__(CONFIG, "sarvam_api_key", "")
        assert synth("hello")["engine"] == "browser"  # verify no SARVAM key fallback
    finally:
        object.__setattr__(CONFIG, "sarvam_api_key", orig)
    assert mock_stt("  namaste  ")["text"] == "namaste"
    assert transcribe(transcript="namaste")["text"] == "namaste"


def test_split_sentences() -> None:
    parts = split_sentences("Pehle dal. Phir roti! Aur? Bas.")
    assert len(parts) == 4
    assert split_sentences("") == [""]
