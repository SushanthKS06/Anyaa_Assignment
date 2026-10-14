"""Kitchen mode: daily execution with the cook. Pure functions over
(plan, household, catalog); the orchestrator owns state + persistence.
Replans ONLY affected meals. Shortfalls feed the next grocery run."""
from __future__ import annotations

import os
import random
import re

from app.engine.adaptations import propose_adaptation
from app.engine.groceries import DISH_ID_RE
from app.engine.models import Household, Plan, PlanDay, Recipe
from app.engine.planner import WEEK, _best_for, _status

# Ingredients that heuristically require a pressure cooker.
# Override via COOKER_ITEMS env var (comma-separated) if your recipe KB differs.
_DEFAULT_COOKER_ITEMS = "rajma,kabuli_chana,chana_dal,toor_dal,moong_dal,masoor_dal,green_moong,matki_sprouts"
COOKER_ITEMS: frozenset[str] = frozenset(
    i.strip() for i in os.environ.get("COOKER_ITEMS", _DEFAULT_COOKER_ITEMS).split(",") if i.strip()
)


def get_day(plan: Plan, weekday: str) -> PlanDay | None:
    return next((d for d in plan.days if d.weekday == weekday), None)


def day_dishes(day: PlanDay, by_id: dict[str, Recipe]) -> list[dict]:
    """Base meals + separate/adaptation plates (parsed from dish_id notes)."""
    out = []
    for m in day.meals:
        r = by_id[m.recipe_id]
        out.append({"slot": m.slot, "recipe": r, "servings": m.servings,
                    "label": "base", "total_min": r.prep_min + r.cook_min})
        extra: dict[str, int] = {}
        for a in m.adaptations:
            mt = DISH_ID_RE.search(a.note)
            if mt and mt.group(1) in by_id:
                extra[mt.group(1)] = extra.get(mt.group(1), 0) + 1
        for did, n in extra.items():
            rr = by_id[did]
            out.append({"slot": m.slot, "recipe": rr, "servings": n,
                        "label": "extra", "total_min": rr.prep_min + rr.cook_min})
    return out


def daily_brief(plan: Plan, household: Household, weekday: str,
                by_id: dict[str, Recipe]) -> dict:
    day = get_day(plan, weekday)
    if day is None:
        return {"ok": False, "error": f"{weekday} plan me nahi"}
    slot_order = {"breakfast": 0, "lunch": 1, "dinner": 2, "snack": 3, "tiffin": 4}
    dishes = sorted(day_dishes(day, by_id),
                    key=lambda d: (slot_order.get(d["slot"], 9), d["label"] == "extra"))
    longest = max(day_dishes(day, by_id), key=lambda d: d["total_min"])["recipe"].name \
        if day_dishes(day, by_id) else "-"
    steps = [f"{d['slot']}: {d['recipe'].name} ({d['servings']} servings, ~{d['total_min']} min)"
             + (" [alag plate]" if d["label"] == "extra" else "")
             for d in dishes]
    reminders = [t.task + f" ({t.deadline})" for m in day.meals for t in m.prep_tasks]
    chunks, cur = [], []
    for s in steps:
        cur.append(s)
        if len(cur) == 3:
            chunks.append(" ... ".join(cur))
            cur = []
    if cur:
        chunks.append(" ... ".join(cur))
    return {"ok": True, "weekday": weekday, "start_first": longest,
            "steps": steps, "reminders": reminders, "spoken": chunks}


def evening_lookahead(plan: Plan, weekday: str, by_id: dict[str, Recipe]) -> dict:
    idx = WEEK.index(weekday)
    nxt = plan.days[idx + 1] if idx + 1 < len(plan.days) else None
    if nxt is None:
        return {"ok": True, "next": None, "tasks": []}
    tasks = []
    for m in nxt.meals:
        r = by_id[m.recipe_id]
        if r.needs_advance_prep:
            qty = next((f"{ing.qty * m.servings:g}{ing.unit}"
                        for ing in r.ingredients if ing.item in COOKER_ITEMS
                        or "soak" in r.needs_advance_prep.lower() and ing.item in
                        {"rajma", "kabuli_chana", "sabudana", "green_moong", "matki_sprouts",
                         "chana_dal", "idli_batter", "dosa_batter"}), "")
            tasks.append(f"{r.name} ({m.slot}): {r.needs_advance_prep}"
                         + (f" — {qty}" if qty else ""))
    return {"ok": True, "next": nxt.weekday, "tasks": tasks}


def _viable_swap(recipes: list[Recipe], household: Household, weekday: str,
                 slot: str, exclude: set[str], want_fast: bool = False) -> Recipe | None:
    nonveg_ok = weekday in household.nonveg_days
    fasting = [m for m in household.members if weekday in m.fasting_days]
    base = [m for m in household.members if m not in fasting] or household.members
    pool = [r for r in recipes if slot in r.meal_types and r.id not in exclude
            and "fasting" not in r.tags]  # vrat dishes never a regular base
    if want_fast:
        pool.sort(key=lambda r: (r.prep_min + r.cook_min))
    rng = random.Random(0)
    for r in (pool if want_fast else sorted(pool, key=lambda x: x.id)):
        st = _status(r, base, weekday, nonveg_ok)
        if all(propose_adaptation(r, m, st[m.name]) is not None or not st[m.name]
               for m in base):
            return r
    return None


def handle_missing_ingredient(plan: Plan, household: Household, weekday: str,
                              item: str, recipes: list[Recipe],
                              by_id: dict[str, Recipe]) -> dict:
    """Find today's meals using the item; swap the first affected to a dish
    without it. Only affected meals change. Shortfall = item still needed
    by other planned meals (approx 2 servings)."""
    day = get_day(plan, weekday)
    if day is None:
        return {"ok": False, "error": f"{weekday} plan me nahi"}
    it = item.lower()
    affected = [m for m in day.meals
                if any(it in ing.item for ing in by_id[m.recipe_id].ingredients)]
    if not affected:
        later = any(any(it in ing.item for ing in by_id[x.recipe_id].ingredients)
                    for d in plan.days for x in d.meals)
        shortfall = [{"item": it, "qty": 500, "unit": "g"}] if later else []
        note = (f"{item} aaj nahi chahiye — hafte me lagega, list me likh diya"
                if later else f"{item} is hafte kahin nahi chahiye")
        return {"ok": True, "swapped": [], "note": note, "shortfall": shortfall}
    m = affected[0]
    alt = _viable_swap([r for r in recipes
                        if not any(it in ing.item for ing in r.ingredients)
                        and "fasting" not in r.tags],
                       household, weekday, m.slot, {m.recipe_id})
    if alt is None:
        return {"ok": False, "error": f"{item} ke bina koi dish nahi mili — bazaar se lao",
                "shortfall": [{"item": it, "qty": 500, "unit": "g"}]}
    old = m.dish
    m.recipe_id, m.dish = alt.id, alt.name
    still_needed = any(any(it in ing.item for ing in by_id[x.recipe_id].ingredients)
                       for d in plan.days for x in d.meals if x is not m)
    shortfall = [{"item": it, "qty": 500, "unit": "g"}] if still_needed else []
    return {"ok": True, "swapped": [{"slot": m.slot, "old": old, "new": alt.name,
                                     "mins": alt.prep_min + alt.cook_min}],
            "shortfall": shortfall}


def handle_extra_guests(plan: Plan, weekday: str, count: int, slot: str,
                        by_id: dict[str, Recipe]) -> dict:
    day = get_day(plan, weekday)
    if day is None:
        return {"ok": False, "error": f"{weekday} plan me nahi"}
    meals = [m for m in day.meals if m.slot == slot] or day.meals
    shortfall = []
    for m in meals:
        m.servings += count
        for ing in by_id[m.recipe_id].ingredients:
            if ing.item == "water":
                continue
            shortfall.append({"item": ing.item, "qty": round(ing.qty * count, 2),
                              "unit": ing.unit})
    return {"ok": True, "slot": slot if any(m.slot == slot for m in day.meals) else "all",
            "added_servings": count,
            "shortfall": shortfall,
            "total_servings": [m.servings for m in meals]}


def handle_equipment_broken(plan: Plan, household: Household, weekday: str,
                            equipment: str, recipes: list[Recipe],
                            by_id: dict[str, Recipe]) -> dict:
    day = get_day(plan, weekday)
    if day is None:
        return {"ok": False, "error": f"{weekday} plan me nahi"}
    eq = equipment.lower()
    if "cooker" in eq or "pressure" in eq:
        cand = [m for m in day.meals
                if {ing.item for ing in by_id[m.recipe_id].ingredients} & COOKER_ITEMS
                or by_id[m.recipe_id].needs_advance_prep]
    else:  # generic breakdown: swap the longest-cook meal for something quick
        cand = sorted(day.meals, key=lambda m: -(by_id[m.recipe_id].prep_min +
                                                 by_id[m.recipe_id].cook_min))[:1]
    if not cand:
        return {"ok": True, "swapped": [], "note": "cooker wali dish aaj hai hi nahi"}
    m = cand[0]
    alt = _viable_swap(recipes, household, weekday, m.slot, {m.recipe_id}, want_fast=True)
    if alt is None:
        return {"ok": False, "error": "quick alternative nahi mili"}
    old = m.dish
    m.recipe_id, m.dish = alt.id, alt.name
    return {"ok": True, "swapped": [{"slot": m.slot, "old": old, "new": alt.name,
                                     "mins": alt.prep_min + alt.cook_min}]}


def handle_cook_leave(plan: Plan, household: Household, weekday: str,
                      recipes: list[Recipe], by_id: dict[str, Recipe]) -> dict:
    day = get_day(plan, weekday)
    if day is None:
        return {"ok": False, "error": f"{weekday} plan me nahi"}
    swapped = []
    for m in day.meals:
        if by_id[m.recipe_id].effort != "low":
            alt = _viable_swap([r for r in recipes if r.effort == "low"],
                               household, weekday, m.slot, {m.recipe_id})
            if alt is not None:
                old = m.dish
                m.recipe_id, m.dish = alt.id, alt.name
                swapped.append({"slot": m.slot, "old": old, "new": alt.name})
    return {"ok": True, "swapped": swapped,
            "note": "sirf low-effort khana" if swapped else "pehle se simple hai"}


TASTE_RES = [
    (re.compile(r"namak.*zyada|too salty|salty"), "less salt next time"),
    (re.compile(r"namak.*kam|bland|feeka"), "more salt next time"),
    (re.compile(r"mirchi.*zyada|too spicy"), "milder next time"),
    (re.compile(r"pasand|love|mast|badhiya|great"), "family liked it — repeat"),
    (re.compile(r"bacho ne nahi|kids (didn't|did not)|waste"), "kids rejected — avoid"),
]


def note_from_feedback(dish: str, note: str) -> str | None:
    for rx, tag in TASTE_RES:
        if rx.search(note.lower()):
            return f"{dish}: {tag} ('{note[:60]}')"
    return f"{dish}: feedback noted ('{note[:60]}')" if note.strip() else None
