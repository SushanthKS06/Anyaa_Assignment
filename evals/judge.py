"""Heuristic judge (PRIMARY in M6 — deterministic, free).
Rubric 0-5: conciseness, one-question discipline, cook-register fit,
recovery acknowledgement, no-AI-speak. An LLM judge (Groq, different family
from the agent) is hooked in llm_judge() but NOT run (no key); a human
spot-check of 2 transcripts is recorded in the M6 report instead."""
from __future__ import annotations


def _replies(transcript: list[dict]) -> list[str]:
    return [e["text"] for e in transcript if e["role"] == "assistant"]


def judge(transcript: list[dict]) -> dict:
    reps = _replies(transcript)
    if not reps:
        return {"overall": 0.0, "n": 0}
    avg_len = sum(len(r) for r in reps) / len(reps)
    conciseness = max(0.0, min(5.0, 5 - max(0, avg_len - 350) / 150))
    one_q = sum(1 for r in reps if r.count("?") <= 2) / len(reps) * 5
    no_ai = 0.0 if any("as an AI" in r or "language model" in r for r in reps) else 5.0
    rec_triggers = [i for i, e in enumerate(transcript)
                    if e["role"] == "user" and any(w in e["text"].lower()
                    for w in ("nahi wait", "galat", "khatm", "kharab", "mehman", "undo"))]
    rec_ok = 0
    for i in rec_triggers:
        nxt = next((transcript[j]["text"] for j in range(i + 1, len(transcript))
                    if transcript[j]["role"] == "assistant"), "")
        if any(w in nxt for w in ("Theek", "Done", "Note kar", "Samajh", "jugaad", "Aaram")):
            rec_ok += 1
    recovery = (rec_ok / len(rec_triggers) * 5) if rec_triggers else 5.0
    scores = {"conciseness": round(conciseness, 2), "one_question": round(one_q, 2),
              "no_ai_speak": no_ai, "recovery": round(recovery, 2)}
    scores["overall"] = round(sum(scores.values()) / len(scores), 2)
    scores["n"] = len(reps)
    return scores


def llm_judge(transcript: list[dict]) -> dict:  # pragma: no cover
    from app.config import CONFIG
    if not CONFIG.groq_api_key:
        raise RuntimeError("no GROQ_API_KEY — heuristic judge only")
    from app.agent.llm import chat
    r = chat([{"role": "system", "content": "Score this assistant transcript 0-5 on personality, naturalness, register fit, recovery, conciseness. Reply JSON."},
              {"role": "user", "content": "\n".join(_replies(transcript)[:20])}],
             role="household", use_mock=False)
    return {"llm": r["text"][:500]}
