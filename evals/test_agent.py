"""M3 agent tests: scripted full flow, dispatch repair, undo, router, extraction."""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from app.agent import tools as T  # noqa: E402
from app.agent.extract import extract, merge_constraints  # noqa: E402
from app.agent.orchestrator import OrchestratorState  # noqa: E402
from app.agent.router import detect_mode  # noqa: E402
from app.engine.models import HouseholdConstraints, Member  # noqa: E402

SCRIPT = [
    "Namaste",
    "Ghar me 4 log hain — Dadi Jain hain aur Thursday ko fast rakhti hain, "
    "Papa diabetic hain, Beta teen hai jo weekend pe nonveg khata hai, aur Chhotu 2 saal ka hai",
    "7 din ka plan banao, budget 6000 ka hai",
    "haan nahi wait, budget 5000 hai",
    "Tuesday dopahar ko paneer nahi, aloo gobhi bana do",
    "yeh kyun choose kiya?",
    "aur",
    "grocery list banao",
    "order karo",
    "haan, order karo",
]


def _scripted() -> OrchestratorState:
    st = OrchestratorState(hid="hh-test-m3")
    for t in SCRIPT:
        st.handle_user(t)
    return st


def test_scripted_full_flow() -> None:
    st = _scripted()
    assert len(st.household.members) == 4
    assert st.household.budget_inr == 5000  # CORRECTION applied
    assert st.plan is not None and len(st.plan.days) == 7
    tue = next(d for d in st.plan.days if d.weekday == "Tue")
    lunch = next(m for m in tue.meals if m.slot == "lunch")
    assert lunch.recipe_id == "aloo_gobhi"  # EDIT applied
    assert st.total > 0 and len(st.cart) > 0
    assert st.stage == "HANDOFF"
    tool_texts = [e["text"] for e in st.transcript if e["role"] == "tool"]
    assert any("place_order" in t for t in tool_texts)
    # confirm-gating: turn 9 asked, turn 10 executed
    replies = [e["text"] for e in st.transcript if e["role"] == "assistant"]
    assert any("Pakka" in r for r in replies), "first order attempt must ask confirm"
    assert any("SM-ORD-" in r for r in replies), "final reply must carry order id"


def test_stockout_surfaced_in_script() -> None:
    st = _scripted()
    assert st.missing, "seeded stock-outs must surface"
    replies = [e["text"] for e in st.transcript if e["role"] == "assistant"]
    assert any("out of stock" in r for r in replies)


def test_transcript_saved(tmp_path) -> None:  # type: ignore[no-untyped-def]
    st = _scripted()
    jl, md = st.save_transcript(str(tmp_path / "t3"))
    import os
    assert os.path.exists(jl) and os.path.exists(md)
    assert len(open(jl, encoding="utf-8").readlines()) == len(st.transcript)


def test_dispatch_repair_and_structured_errors() -> None:
    st = OrchestratorState(hid="hh-test-repair")
    assert T.dispatch(st, "nope", {})["ok"] is False
    r = T.dispatch(st, "swap_meal", {"day": " Funday ", "slot": "lunch", "new_dish": ""})
    assert r["ok"] is False and "error" in r  # no crash on bad day
    r2 = T.dispatch(st, "set_constraint", {"member_name": "Nobody", "field": "diet", "value": "veg"})
    assert r2["ok"] is False
    st.household.members.append(Member(name="A", age_group="adult", diet="veg"))
    r3 = T.dispatch(st, "set_constraint", {"member_name": "A", "field": "diet", "value": "keto"})
    assert r3["ok"] is False  # invalid diet rejected, member unchanged
    assert st.household.members[0].diet == "veg"
    r4 = T.dispatch(st, "place_order", {"confirm": True})
    assert r4["ok"] is False and r4.get("need_confirm") is not True  # empty cart, not confirm path


def test_edit_cart_and_undo() -> None:
    st = OrchestratorState(hid="hh-test-undo")
    st.household.members.append(Member(name="A", age_group="adult", diet="veg"))
    assert T.dispatch(st, "generate_plan", {"days": 3, "seed": 1})["ok"] is True
    assert T.dispatch(st, "build_grocery_list", {"seed": 5})["ok"] is True
    total0 = st.total
    sku = st.cart[0]["sku"]
    T.dispatch(st, "edit_cart", {"sku": sku, "packs": st.cart[0]["packs"] + 1})
    assert st.total >= total0
    r = T.dispatch(st, "undo", {})
    assert r["ok"] is True and abs(st.total - total0) < 1e-6


def test_router_modes() -> None:
    assert detect_mode("maine khana bana diya")[0] == "cook"
    assert detect_mode("/cook")[0] == "cook"
    assert detect_mode("/home", "cook") == ("household", True)
    assert detect_mode("grocery list banao", "cook")[0] == "household"
    assert detect_mode("aur batao", "household")[0] == "household"


def test_correction_merge_no_placeholder_growth() -> None:
    base = HouseholdConstraints()
    c1 = extract("Dadi Jain hain, budget 6000 ka hai", base)
    assert c1.budget_inr == 6000
    c2 = extract("haan nahi wait, budget 5000 hai", c1)
    assert c2.budget_inr == 5000
    names = [m.name for m in c2.members]
    assert "Member1" not in names and len(names) == len(set(names))
    merged = merge_constraints(c1, extract("budget 5000 hai", HouseholdConstraints()))
    assert merged.budget_inr == 5000
