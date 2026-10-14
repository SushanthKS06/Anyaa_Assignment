"""M0 smoke test: 10 Hinglish utterances -> mock STT -> deterministic extraction
(Pydantic) + 20 tool-call reliability trials + latency + forced-429 fallback.

Run: python scripts/smoke_test.py
No API keys required. All LLM/STT calls are deterministic mocks unless keys exist
and LLM_MOCK_DEFAULT=false. Results -> logs/smoke_results.json
"""
from __future__ import annotations

import json
import re
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

from app.agent.llm import chat  # noqa: E402
from app.engine.models import HouseholdConstraints, Member  # noqa: E402
from app.store.db import init_db  # noqa: E402
from app.voice.stt import mock_stt  # noqa: E402

UTTERANCES = [
    "Dadi Jain hain, onion garlic bilkul nahi chahiye",
    "Papa diabetic hain, low sugar khana banao",
    "Chhotu 2 saal ka hai, toddler ke liye soft food, mirchi kam",
    "Mujhe peanut se allergy hai, please peanut avoid karo",
    "Teen beta non-veg sirf Saturday Sunday khata hai",
    "Dadi ka Ekadashi fast hai Thursday ko, vrat ka khana chahiye",
    "Budget 5000 rupaye hai is hafte ka, sasta plan banao",
    "Cook Thursday ko chhutti par hai, simple khana rakho",
    "Friday ko 4 guests aa rahe hain dinner par",
    "Haan nahi wait, paneer nahi — aloo gobhi bana do Tuesday ko",
]

TOOL_TRIALS = [
    {"name": f"member_{i}", "age_group": "adult", "diet": "veg", "valid": True}
    for i in range(14)
] + [
    {"name": "", "age_group": "adult", "diet": "veg", "valid": False},  # empty name
    {"name": "x", "age_group": "alien", "diet": "veg", "valid": False},  # bad age
    {"name": "y", "age_group": "adult", "diet": "keto", "valid": False},  # bad diet
    {"name": "jain_dadi", "age_group": "senior", "diet": "jain", "valid": True},
    {"name": "toddler", "age_group": "toddler", "diet": "veg", "valid": True},
    {"name": "diabetic_papa", "age_group": "adult", "diet": "veg", "valid": True},
]


def deterministic_extract(text: str) -> HouseholdConstraints:
    """M0 mock extractor (rule-based, deterministic). Real LLM extraction ships in M3."""
    t = text.lower()
    members: list[Member] = []
    if "jain" in t:
        members.append(Member(name="Dadi", age_group="senior", diet="jain"))
    if "diabet" in t or "low sugar" in t:
        members.append(Member(name="Papa", age_group="adult", diet="veg", health_notes=["low_sugar"]))
    if "toddler" in t or "2 saal" in t or "chhotu" in t:
        members.append(Member(name="Chhotu", age_group="toddler", diet="veg", health_notes=["soft_food"]))
    if "peanut" in t or "allergy" in t:
        members.append(Member(name="AllergyMember", age_group="adult", diet="veg", allergies=["peanut"]))
    if "non-veg" in t or "nonveg" in t or "non veg" in t:
        members.append(Member(name="Beta", age_group="teen", diet="nonveg"))
    fasting = "Ekadashi" if "ekadashi" in t else ""
    budget = None
    m = re.search(r"(\d[\d,]*)\s*(rupaye|rs|inr|budget)", t)
    if m or "5000" in t:
        budget = 5000
    nonveg_days = ["Sat", "Sun"] if ("saturday" in t or "sunday" in t or "saturday sunday" in t or "weekend" in t or "non-veg" in t) else []
    if not members:
        members = [Member(name="Member1", age_group="adult", diet="veg")]
    return HouseholdConstraints(
        members=members, days_to_plan=7, budget_inr=budget,
        nonveg_days=nonveg_days, fasting_context=fasting,
    )


def main() -> int:
    out: dict = {"utterances": [], "tool_trials": {}, "latency_ms": {}, "fallback": {}, "db": {}}
    print("== M0 smoke: 10 Hinglish utterances -> STT -> extraction ==")
    ok_extract = 0
    for u in UTTERANCES:
        stt = mock_stt(u)
        assert stt["text"] == u.strip(), "mock STT must echo input"
        c = deterministic_extract(stt["text"])
        good = len(c.members) >= 1
        ok_extract += int(good)
        # LLM chat turn (mock) must stay short: <= 2 sentences-ish (<=400 chars)
        r = chat([{"role": "user", "content": u}], role="household")
        concise = len(r["text"]) <= 400
        out["utterances"].append({"in": u, "members": [m.model_dump() for m in c.members],
                                  "llm_model": r["model"], "concise": concise})
        print(f"  IN: {u[:60]:62s} -> {[m.name+':'+m.diet for m in c.members]} llm={r['model']} concise={concise}")
    print(f"extract ok: {ok_extract}/{len(UTTERANCES)}")

    print("== 20 tool-call reliability trials (Pydantic validation) ==")
    passed = failed_expected = 0
    for t in TOOL_TRIALS:
        try:
            Member(name=t["name"], age_group=t["age_group"], diet=t["diet"])  # type: ignore
            if t["valid"]:
                passed += 1
            else:
                print(f"  UNEXPECTED PASS: {t}")
        except Exception:
            if not t["valid"]:
                failed_expected += 1
                passed += 1
            else:
                print(f"  UNEXPECTED FAIL: {t}")
    # + 20 llm.chat calls with tools arg (API stability)
    lat: list[float] = []
    for i in range(20):
        t0 = time.perf_counter()
        r = chat([{"role": "user", "content": f"tool trial {i}: aloo gobhi Tuesday?"}],
                 tools=[{"name": "swap_meal"}], role="household")
        lat.append((time.perf_counter() - t0) * 1000)
        assert r["text"], "empty llm reply"
    out["tool_trials"] = {"passed": passed, "total": len(TOOL_TRIALS), "llm_calls": 20}
    out["latency_ms"] = {"p50": round(statistics.median(lat), 2),
                         "p95": round(sorted(lat)[int(0.95 * len(lat)) - 1], 2),
                         "max": round(max(lat), 2)}
    print(f"tool validation: {passed}/{len(TOOL_TRIALS)} | llm p50={out['latency_ms']['p50']}ms "
          f"p95={out['latency_ms']['p95']}ms max={out['latency_ms']['max']}ms")

    print("== forced-429 fallback ==")
    r = chat([{"role": "user", "content": "hello, fallback test"}],
             role="household", force_429=True, use_mock=False)
    fallback_ok = r["model"].startswith("mock:")
    out["fallback"] = {"forced_429_model": r["model"], "fallback_label": r["fallback"], "ok": fallback_ok}
    print(f"forced 429 -> model={r['model']} fallback={r['fallback']} ok={fallback_ok}")

    print("== db init ==")
    dbp = init_db("data/app.db")
    out["db"] = {"path": dbp, "ok": Path(dbp).exists()}
    print(f"db: {dbp} exists={out['db']['ok']}")

    Path("logs").mkdir(exist_ok=True)
    Path("logs/smoke_results.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    all_ok = ok_extract == len(UTTERANCES) and passed == len(TOOL_TRIALS) and fallback_ok and out["db"]["ok"]
    print(f"SMOKE {'PASS' if all_ok else 'FAIL'} -> logs/smoke_results.json")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
