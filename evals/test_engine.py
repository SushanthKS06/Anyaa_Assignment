"""M1 engine tests: zero hard violations, adaptations, repeats, reasons, determinism."""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from app.engine.constraints import member_violations  # noqa: E402
from app.engine.models import CookProfile, Household, Member  # noqa: E402
from app.engine.planner import REPEAT_WINDOW, generate_plan, load_recipes  # noqa: E402
from evals.fixtures import patel_navratri, sen_family, sharma_joint  # noqa: E402
from scripts.validate_recipes import validate  # noqa: E402

RECIPES = load_recipes()
BY_ID = {r.id: r for r in RECIPES}


def _plans() -> dict[str, tuple[Household, object]]:
    return {
        "sharma": (sharma_joint(), generate_plan(sharma_joint(), RECIPES, seed=42)),
        "sen": (sen_family(), generate_plan(sen_family(), RECIPES, seed=42)),
        "patel": (patel_navratri(), generate_plan(patel_navratri(), RECIPES, seed=42)),
    }


def test_kb_size_and_validator_clean() -> None:
    assert 40 <= len(RECIPES) <= 60, f"KB size {len(RECIPES)} outside 40-60"
    errors, _review = validate()
    assert errors == [], f"validator errors: {errors[:5]}"


def test_zero_hard_violations_and_full_coverage() -> None:
    """Nobody eats a violating base silently: every violation must have an
    adaptation (portion fix or separate dish), and zero CONFLICTs."""
    for name, (hh, plan) in _plans().items():  # type: ignore
        for day in plan.days:  # type: ignore
            nonveg_ok = day.weekday in hh.nonveg_days
            for meal in day.meals:
                r = BY_ID[meal.recipe_id]
                assert meal.slot in r.meal_types
                adapted = {a.member for a in meal.adaptations}
                assert meal.conflict == "", f"{name} d{day.day_index} {meal.slot}: {meal.conflict}"
                for m in hh.members:
                    fasting = day.weekday in m.fasting_days
                    v = member_violations(r, m, day.weekday, nonveg_ok, fasting)
                    if v:
                        assert m.name in adapted, (
                            f"{name} d{day.day_index} {meal.slot} {r.id}: "
                            f"{m.name} violations {v} with no adaptation")
                # allergy members never get a shared "portion" — only separate dish
                for m in hh.members:
                    if not m.allergies:
                        continue
                    for a in meal.adaptations:
                        if a.member == m.name:
                            assert "separate" in a.change or "CONFLICT" in a.change, (
                                f"allergy member {m.name} got portion adaptation: {a.change}")


def test_repeat_window_and_daily_variety() -> None:
    for name, (_hh, plan) in _plans().items():  # type: ignore
        for slot in ("breakfast", "lunch", "dinner"):
            ids = [m.recipe_id for day in plan.days for m in day.meals if m.slot == slot]  # type: ignore
            for i, rid in enumerate(ids):
                assert rid not in ids[max(0, i - REPEAT_WINDOW):i], (
                    f"{name} {slot}: {rid} repeated within {REPEAT_WINDOW} days")
        for day in plan.days:  # type: ignore
            ids = [m.recipe_id for m in day.meals]
            assert len(ids) == len(set(ids)), f"{name} d{day.day_index}: same dish twice in a day"


def test_reasons_trace_complete() -> None:
    for name, (_hh, plan) in _plans().items():  # type: ignore
        assert len(plan.reasons) == 7 * 3, f"{name}: {len(plan.reasons)} reasons"  # type: ignore
        for rs in plan.reasons:  # type: ignore
            assert rs.why, f"{name} d{rs.day_index} {rs.slot}: empty why"


def test_deterministic_same_seed() -> None:
    hh = sharma_joint()
    p1 = generate_plan(hh, RECIPES, seed=7)
    p2 = generate_plan(hh, RECIPES, seed=7)
    assert p1.model_dump() == p2.model_dump()


def test_prep_tasks_for_advance_dishes() -> None:
    from app.engine.planner import _prep_tasks
    rajma = BY_ID["rajma_chawal"]
    tasks = _prep_tasks(rajma, 2)
    assert len(tasks) == 1 and "night before" in tasks[0].deadline
    assert _prep_tasks(BY_ID["dal_tadka"], 0) == []
    for _name, (_hh, plan) in _plans().items():  # type: ignore
        for day in plan.days:  # type: ignore
            for meal in day.meals:
                if BY_ID[meal.recipe_id].needs_advance_prep:
                    assert meal.prep_tasks, f"{meal.recipe_id} missing prep tasks"


def test_fasting_members_get_vrat_plate() -> None:
    hh, plan = _plans()["patel"]  # type: ignore
    mon = plan.days[0]  # Monday  # type: ignore
    assert mon.weekday == "Mon"
    for meal in mon.meals:
        adapted = {a.member for a in meal.adaptations}
        for m in ("Kaka", "Kaki", "Ba"):
            assert m in adapted, f"Mon {meal.slot}: fasting {m} has no plate"


def test_servings_scale_with_guests() -> None:
    hh, plan = _plans()["patel"]  # type: ignore
    fri = [d for d in plan.days if d.weekday == "Fri"][0]  # type: ignore
    for meal in fri.meals:
        assert meal.servings == 8, f"Fri servings {meal.servings} != 4 members + 4 guests"
    hh1, plan1 = _plans()["sharma"]  # type: ignore
    for day in plan1.days:  # type: ignore
        for meal in day.meals:
            assert meal.servings == 5


def test_all_fasting_household_gets_vrat_base() -> None:
    hh = Household(members=[Member(name="Solo", age_group="adult", diet="veg",
                                           fasting_days=["Mon", "Tue", "Wed", "Thu",
                                                         "Fri", "Sat", "Sun"])])
    plan = generate_plan(hh, RECIPES, days=2, seed=3)
    for day in plan.days:
        for meal in day.meals:
            assert "fasting" in BY_ID[meal.recipe_id].tags, f"{meal.recipe_id} not vrat-safe"


def test_jain_meat_never_portioned() -> None:
    from app.engine.adaptations import propose_adaptation
    chicken = BY_ID["chicken_curry"]
    dadi = Member(name="Dadi", age_group="senior", diet="jain")
    assert propose_adaptation(chicken, dadi, ["diet:jain"]) is None
    beta = Member(name="Beta", age_group="teen", diet="nonveg")
    assert propose_adaptation(chicken, beta, []) is None  # no violations, no adaptation


def test_weekend_nonveg_side_present() -> None:
    _hh, plan = _plans()["sharma"]  # type: ignore
    wknd = [d for d in plan.days if d.weekday in ("Sat", "Sun")]  # type: ignore
    sides = [a for d in wknd for m in d.meals if m.slot in ("lunch", "dinner")
             for a in m.adaptations if "weekend nonveg side" in a.change and a.member == "Beta"]
    assert sides, "Beta (teen nonveg) got no weekend nonveg side"


def test_cook_leave_day_is_low_effort() -> None:
    hh, plan = _plans()["sharma"]  # type: ignore
    thu = [d for d in plan.days if d.weekday == "Thu"][0]  # type: ignore
    for meal in thu.meals:
        assert BY_ID[meal.recipe_id].effort == "low", f"leave-day {meal.recipe_id} not low effort"
