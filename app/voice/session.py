"""Voice session: one OrchestratorState per socket + async sentence stream.
Barge-in: client sends interrupt -> generator stops, last assistant turn is
truncated in history to what was reportedly spoken. Text turns use the exact
same core as the CLI (text parity by construction)."""
from __future__ import annotations

import asyncio
import re
import time

from app.agent.orchestrator import OrchestratorState
from app.voice.tts import synth

def clean_for_tts(text: str) -> str:
    # Remove markdown formatting characters
    t = re.sub(r"[*#_~`]", "", text)
    t = re.sub(r"•\s*", "", t)
    # Currency symbols to natural words
    t = t.replace("₹", "Rs. ")
    t = re.sub(r"\s+", " ", t).strip(" \t|;—\n")
    return t


def split_sentences(text: str) -> list[str]:
    # Split on sentence boundaries (. ! ? । | or newlines) without breaking decimals like 1.5
    raw = re.split(r"(?<=[!?।|\n])\s*|(?<=\.)\s+(?![0-9])", text)
    out: list[str] = []
    for p in raw:
        cleaned = clean_for_tts(p)
        if len(cleaned) >= 2:
            out.append(cleaned)
    return out or [clean_for_tts(text)]


class VoiceSession:
    def __init__(self, hid: str | None = None, lang: str = "hi-IN") -> None:
        self.st = OrchestratorState(hid=hid or f"hh-ws-{int(time.time())}")
        self.interrupted = False
        self.model = "mock:deterministic"
        self.latency_ms = 0.0
        self.lang = lang

    def snapshot(self) -> dict:
        st = self.st
        return {
            "stage": st.stage, "mode": st.mode,
            "members": [m.model_dump() for m in st.household.members],
            "budget": st.household.budget_inr,
            "days": st.days_to_plan,
            "plan": ([{"weekday": d.weekday,
                       "meals": [{"slot": m.slot, "dish": m.dish, "servings": m.servings,
                                  "adaptations": [a.model_dump() for a in m.adaptations]}
                                 for m in d.meals]} for d in st.plan.days]
                      if st.plan else []),
            "cart": st.cart, "total": st.total, "missing": st.missing,
            "shortfalls": st.shortfalls, "taste_notes": st.taste_notes,
            "lang": self.lang,
        }

    async def turn(self, text: str, voice: bool = True, lang: str | None = None):
        """Yield events: assistant -> state -> tools -> tts* . Checks interrupt."""
        if lang and lang != "auto":
            self.st.lang = lang
            self.lang = lang
        t0 = time.perf_counter()
        before = len(self.st.transcript)
        reply = self.st.handle_user(text)
        self.latency_ms = (time.perf_counter() - t0) * 1000
        active_lang = getattr(self.st, "lang", "hi-IN")
        self.lang = active_lang
        from app.config import CONFIG as _C
        live = bool((_C.gemini_api_key or _C.groq_api_key) and not _C.mock_default)
        self.model = "llm:live" if live else "mock:deterministic"
        yield {"type": "assistant", "text": reply, "latency_ms": round(self.latency_ms, 1),
               "model": self.model, "lang": active_lang}
        new_tools = [e for e in self.st.transcript[before:] if e["role"] == "tool"]
        yield {"type": "tools", "calls": [
            {"text": e["text"], "ok": (e.get("tools") or [{}])[0].get("result", {}).get("ok")}
            for e in new_tools]}
        yield {"type": "state", "state": self.snapshot()}
        if voice:
            for s in split_sentences(reply):
                if self.interrupted:
                    break
                await asyncio.sleep(0)
                yield {"type": "tts", **synth(s, language_code=active_lang)}

    def interrupt(self, spoken_chars: int = 0) -> dict:
        self.interrupted = True
        for e in reversed(self.st.transcript):
            if e["role"] == "assistant":
                full = e["text"]
                e["text"] = (full[:spoken_chars] + " …[interrupted]"
                             if spoken_chars < len(full) else full)
                return {"type": "interrupted", "truncated_to": len(e["text"])}
        return {"type": "interrupted", "truncated_to": 0}

    def reset_interrupt(self) -> None:
        self.interrupted = False
