"""Simulated users: deterministic scripted personas (no keys needed).
Each scenario's turns already encode persona behavior (vague first answers,
corrections, cook-voice disruptions). With a GROQ key, SimUser.llm_turn()
lets llama-3.3-70b-versatile improvise adversarial turns — not exercised here
(no key), so all M6 results rest on the scripted users below. Honest label:
mock sim users."""
from __future__ import annotations


class SimUser:
    def __init__(self, turns: list[str]) -> None:
        self._turns = list(turns)

    def turns(self) -> list[str]:
        return list(self._turns)

    def llm_turn(self, history: list[dict]) -> str:  # pragma: no cover
        from app.config import CONFIG
        if not CONFIG.groq_api_key:
            raise RuntimeError("no GROQ_API_KEY — scripted turns only")
        from app.agent.llm import chat
        r = chat([{"role": "system", "content": "You are a messy Indian household member. Reply with ONE short Hinglish utterance."}] +
                 [{"role": m["role"], "content": m["text"]} for m in history[-6:]],
                 role="household", use_mock=False)
        return r["text"]
