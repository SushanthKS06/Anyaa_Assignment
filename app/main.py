"""FastAPI entry: health, cockpit, WebSocket voice/text session.
One VoiceSession per socket (own household state). Text turns and voice turns
hit the identical orchestrator core."""
from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from app.config import CONFIG
from app.voice.session import VoiceSession

app = FastAPI(title="Rasoi — Household Meal Voice Agent")


@app.get("/health")
def health() -> dict:
    live = bool((CONFIG.gemini_api_key or CONFIG.groq_api_key) and not CONFIG.mock_default)
    return {"status": "ok", "milestone": "M5", "voice": CONFIG.voice_enabled,
            "llm": "live" if live else "mock:deterministic",
            "stt_tts": "sarvam" if CONFIG.sarvam_api_key else "browser-webspeech",
            "has_sarvam": bool(CONFIG.sarvam_api_key)}


@app.get("/api/info")
def info() -> dict:
    sim = ["instamart-order", "whatsapp-send"]
    if not CONFIG.sarvam_api_key:
        sim.append("sarvam-stt/tts-no-key")
    return health() | {"simulated": sim, "has_sarvam": bool(CONFIG.sarvam_api_key)}


@app.get("/", response_class=HTMLResponse)
def cockpit() -> str:
    try:
        return open("web/index.html", encoding="utf-8").read()
    except FileNotFoundError:
        return "<h1>Cockpit missing — run from repo root.</h1>"


@app.websocket("/ws")
async def ws(ws: WebSocket) -> None:
    await ws.accept()
    sess = VoiceSession()
    await ws.send_json({"type": "ready", "state": sess.snapshot(),
                        "model": sess.model, "simulated": True,
                        "has_sarvam": bool(CONFIG.sarvam_api_key)})
    try:
        while True:
            msg = await ws.receive_json()
            kind = msg.get("type")
            if kind == "user_text":
                sess.reset_interrupt()
                lang = msg.get("lang") or sess.lang
                sess.lang = lang
                async for ev in sess.turn(str(msg.get("text", "")),
                                         voice=bool(msg.get("voice", True)),
                                         lang=lang):
                    await ws.send_json(ev)
                    if ev["type"] == "assistant" and sess.interrupted:
                        break
            elif kind == "user_audio":
                sess.reset_interrupt()
                from app.voice.stt import transcribe
                b64 = msg.get("audio_b64", "")
                lang = msg.get("lang") or sess.lang
                stt_lang = "unknown" if lang == "auto" else lang
                t_res = transcribe(audio_b64=b64, language_code=stt_lang)
                text = t_res.get("text", "")
                await ws.send_json({"type": "transcription", "text": text, "engine": t_res.get("engine"), "lang": lang})
                if text:
                    async for ev in sess.turn(text, voice=bool(msg.get("voice", True)), lang=lang):
                        await ws.send_json(ev)
                        if ev["type"] == "assistant" and sess.interrupted:
                            break
            elif kind == "language":
                sess.lang = msg.get("lang", "hi-IN")
                await ws.send_json({"type": "language", "lang": sess.lang})
            elif kind == "interrupt":
                await ws.send_json(sess.interrupt(int(msg.get("spoken_chars", 0))))
            elif kind == "mode":
                m = msg.get("mode", "household")
                sess.st.mode = m if m in ("household", "cook") else "household"
                await ws.send_json({"type": "state", "state": sess.snapshot()})
                cmd = "/cook" if sess.st.mode == "cook" else "/home"
                async for ev in sess.turn(cmd, voice=bool(msg.get("voice", True)), lang=sess.lang):
                    await ws.send_json(ev)
            elif kind == "new_session":
                sess = VoiceSession(lang=sess.lang)
                await ws.send_json({"type": "ready", "state": sess.snapshot(),
                                    "model": sess.model, "simulated": True,
                                    "has_sarvam": bool(CONFIG.sarvam_api_key)})
            else:
                await ws.send_json({"type": "error", "error": f"unknown msg: {kind}"})
    except WebSocketDisconnect:
        pass
