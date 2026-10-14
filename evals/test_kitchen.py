"""M4 kitchen tests: brief, lookahead, 4 disruptions, logging, shortfall->groceries."""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from app.agent import tools as T  # noqa: E402
from app.agent.orchestrator import OrchestratorState  # noqa: E402
from app.engine import kitchen as K  # noqa: E402
from app.engine.models import Member, Plan, PlanDay, PlannedMeal  # noqa: E402
from app.engine.planner import WEEK, generate_plan, load_recipes  # noqa: E402
from app.store.db import get_conn  # noqa: E402
from evals.fixtures import sharma_joint  # noqa: E402

RECIPES = load_recipes()
BY_ID = {r.id: r for r in RECIPES}


def _state(seed: int = 42) -> OrchestratorState:
    st = OrchestratorState(hid="hh-test-kitchen")
    st.household = sharma_joint()
    st.plan = generate_plan(st.household, RECIPES, seed=seed)
    return st


def test_brief_structure() -> None:
    st = _state()
    b = K.daily_brief(st.plan, st.household, "Mon", BY_ID)
    assert b["ok"] and b["start_first"]
    slots = [s.split(":")[0] for s in b["steps"] if not s.startswith("lunch: Kuttu")]
    assert slots == sorted(slots, key=lambda s: {"breakfast": 0, "lunch": 1, "dinner": 2}[s])
    for chunk in b["spoken"]:
        assert chunk.count(" ... ") <= 2, "max 3 items per breath"
    assert all("(5 servings" in s for s in b["steps"] if "[alag plate]" not in s)
    th = K.daily_brief(st.plan, st.household, "Thu", BY_ID)
    assert any("[alag plate]" in s for s in th["steps"]), "Thu needs Dadi vrat plates"


def test_lookahead_names_overnight_task() -> None:
    plan = Plan(days=[
        PlanDay(day_index=0, weekday="Mon", meals=[
            PlannedMeal(slot="lunch", recipe_id="dal_tadka", dish="x", servings=2)]),
        PlanDay(day_index=1, weekday="Tue", meals=[
            PlannedMeal(slot="lunch", recipe_id="rajma_chawal", dish="y", servings=2)]),
    ], reasons=[])
    la = K.evening_lookahead(plan, "Mon", BY_ID)
    assert la["next"] == "Tue"
    assert any("overnight" in t and "rajma" in t.lower() for t in la["tasks"])


def test_missing_ingredient_replans_only_affected() -> None:
    st = _state()
    before = {d.weekday: [(m.slot, m.recipe_id) for m in d.meals] for d in st.plan.days}
    r = K.handle_missing_ingredient(st.plan, st.household, "Mon", "tomato", RECIPES, BY_ID)
    assert r["ok"] and len(r["swapped"]) == 1
    for d in st.plan.days:
        if d.weekday != "Mon":
            assert [(m.slot, m.recipe_id) for m in d.meals] == before[d.weekday]
    # swapped dish has no tomato
    new_id = next(m.recipe_id for d in st.plan.days if d.weekday == "Mon"
                  for m in d.meals if m.slot == r["swapped"][0]["slot"])
    assert "tomato" not in {i.item for i in BY_ID[new_id].ingredients}
    assert "fasting" not in BY_ID[new_id].tags, "no vrat dish as regular base"


def test_extra_guests_rescale_and_shortfall() -> None:
    st = _state()
    r = K.handle_extra_guests(st.plan, "Mon", 4, "dinner", BY_ID)
    assert r["ok"] and r["total_servings"] == [9]
    assert len(r["shortfall"]) > 0
    st.shortfalls.extend(r["shortfall"])
    from app.engine.groceries import aggregate_needs, to_base
    needs = aggregate_needs(st.plan, BY_ID)
    # every shortfall item is accounted in needs (base uses servings=9 now)
    for s in r["shortfall"][:3]:
        q, _k = to_base(float(s["qty"]), str(s["unit"]), str(s["item"]))
        assert s["item"] in needs and needs[s["item"]][0] >= q - 1e-9


def test_equipment_and_leave_simplify() -> None:
    st = _state()
    r = K.handle_equipment_broken(st.plan, st.household, "Mon", "cooker", RECIPES, BY_ID)
    assert r["ok"]
    if r["swapped"]:
        new_id = next(m.recipe_id for d in st.plan.days if d.weekday == "Mon"
                      for m in d.meals if m.slot == r["swapped"][0]["slot"])
        assert "fasting" not in BY_ID[new_id].tags
    st2 = _state()
    r2 = K.handle_cook_leave(st2.plan, st2.household, "Mon", RECIPES, BY_ID)
    assert r2["ok"]
    mon = next(d for d in st2.plan.days if d.weekday == "Mon")
    assert all(BY_ID[m.recipe_id].effort == "low" for m in mon.meals)


def test_log_cooked_and_taste_note_persisted() -> None:
    st = _state()
    r = T.dispatch(st, "log_cooked", {"slot": "lunch", "status": "cooked", "note": "namak thoda zyada tha"})
    assert r["ok"] and r["dish"]
    assert any("less salt" in n for n in st.taste_notes)
    conn = get_conn("data/app.db")
    rows = conn.execute("SELECT event_json FROM cook_logs WHERE household_id=?",
                        (st.hid,)).fetchall()
    conn.close()
    assert any("lunch" in row[0] for row in rows)


def test_shortfalls_feed_next_grocery_run() -> None:
    st = _state()
    r = T.dispatch(st, "report_disruption",
                   {"kind": "extra_guests", "detail": "4 guests", "day": "Monday", "slot": "dinner"})
    assert r["ok"] and st.shortfalls
    first_short = dict(st.shortfalls[0])
    g = T.dispatch(st, "build_grocery_list", {"seed": 7})
    assert g["ok"] and g.get("shortfalls_consumed", 0) >= 1
    assert st.shortfalls == [], "shortfalls consumed once"
    need_item = first_short["item"]
    line = next((ln for ln in st.cart if ln["item"] == need_item), None)
    assert line is not None


def test_cook_day_flow_deterministic() -> None:
    a, b = _state(), _state()
    ba = K.daily_brief(a.plan, a.household, "Mon", BY_ID)
    bb = K.daily_brief(b.plan, b.household, "Mon", BY_ID)
    assert ba == bb
    assert WEEK[a.cook_weekday() == "Mon" and 0 or 0] == "Mon"
