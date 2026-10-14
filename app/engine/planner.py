"""Deterministic planner: filter (hard) -> score (soft) -> greedy fill with
repeat window -> swap pass (effort cap, ingredient count) -> adaptations +
prep tasks -> plan + machine-readable reasons trace. Seeded deterministic."""
from __future__ import annotations

import json
import random

from app.engine.adaptations import propose_adaptation
from app.engine.constraints import EFFORT_RANK, SOFT_WEIGHTS, member_violations
from app.engine.models import (
    Adaptation,
    Household,
    Member,
    Plan,
    PlanDay,
    PlannedMeal,
    PrepTask,
    Reason,
    Recipe,
)

WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
REPEAT_WINDOW = 3  # no repeat of same dish in same slot within N days
MAX_EFFORT_PER_DAY = 4  # sum of effort ranks across main slots


def load_recipes(path: str = "app/data/recipes.json") -> list[Recipe]:
    return [Recipe.model_validate(r) for r in json.loads(open(path, encoding="utf-8").read())]


def _is_fasting(member: Member, weekday: str) -> bool:
    return weekday in member.fasting_days


def _status(recipe: Recipe, members: list[Member], weekday: str,
            nonveg_allowed: bool) -> dict[str, list[str]]:
    """member name -> violations (empty = eats base as-is)."""
    out: dict[str, list[str]] = {}
    for m in members:
        out[m.name] = member_violations(
            recipe, m, weekday, nonveg_allowed,
            fasting_day=_is_fasting(m, weekday))
    return out


def _score(recipe: Recipe, members: list[Member], recent_ids: list[str],
           leave_day: bool, skill: str, rng: random.Random,
           force_nv_primary: bool = False) -> tuple[float, list[str]]:
    w = SOFT_WEIGHTS
    s = 0.0
    why: list[str] = []
    if recipe.id in recent_ids:
        s -= 2 * w["variety"]
    else:
        s += w["variety"]
        why.append(f"no repeat in {REPEAT_WINDOW}-day window")
    if leave_day:
        if recipe.effort == "low":
            s += w["effort_fit"]
            why.append("low effort — cook leave day")
        else:
            s -= 3 * w["effort_fit"]
    elif skill == "basic":
        s += {"low": 2.0, "medium": 0.5, "high": -3.0}[recipe.effort]
    elif skill == "expert" and recipe.effort == "high":
        s += 1.0
    else:
        s += {"low": 1.0, "medium": 1.0, "high": 0.0}[recipe.effort]
    if recipe.leftover_friendly:
        s += 0.5 * w["leftover"]
        why.append("leftover-friendly")
    if any(m.age_group in ("toddler", "child") for m in members) and "kid_ok" in recipe.tags:
        s += w["preference"]
        why.append("kid-approved")
    if any("low_sugar" in m.health_notes for m in members) and "diabetic_ok" in recipe.tags:
        s += w["preference"]
        why.append("diabetic-friendly")
    if len(recipe.ingredients) <= 5:
        s += 0.5 * w["budget"]
        why.append("few ingredients — cheap, less waste")
    nv_count = sum(1 for m in members if m.diet == "nonveg")
    veg_count = sum(1 for m in members if m.diet in ("veg", "jain", "vegan"))
    adult_nv = sum(1 for m in members if m.age_group == "adult" and m.diet == "nonveg")
    adult_all = sum(1 for m in members if m.age_group == "adult")
    is_nonveg_primary = (
        force_nv_primary or
        (nv_count > veg_count) or
        (adult_all > 0 and adult_nv == adult_all and nv_count > 0)
    )
    if nv_count > 0 and ("nonveg" in recipe.tags or "eggetarian" in recipe.tags):
        if is_nonveg_primary:
            s += 8.0 + 2.0 * nv_count
            why.append(f"prefer nonveg main ({nv_count} nonveg members)")
        else:
            s += w.get("nonveg_weekend", 2.5)
            why.append("nonveg preference")
    if recipe.needs_advance_prep:
        s -= 0.25 * w["prep_fit"]
    s += rng.random() * 0.01  # seeded tie-break only
    return s, why


def _prep_tasks(recipe: Recipe, day_index: int) -> list[PrepTask]:
    if not recipe.needs_advance_prep:
        return []
    txt = recipe.needs_advance_prep.lower()
    deadline = "night before (by 10pm)" if "overnight" in txt else "same day morning"
    return [PrepTask(task=f"{recipe.name}: {recipe.needs_advance_prep}",
                     deadline=deadline, day_index=day_index)]


def _best_for(recipe_pool: list[Recipe], members: list[Member], weekday: str,
              nonveg_allowed: bool, slot: str | None, recent: list[str],
              leave_day: bool, skill: str, rng: random.Random) -> Recipe | None:
    cands = [r for r in recipe_pool if slot is None or slot in r.meal_types]
    viable = [r for r in cands if all(not _status(r, members, weekday, nonveg_allowed)[m.name]
                                     for m in members)]
    if not viable:
        return None
    scored = [(_score(r, members, recent, leave_day, skill, rng)[0], r) for r in viable]
    scored.sort(key=lambda t: (-t[0], t[1].id))
    return scored[0][1]


def generate_plan(household: Household, recipes: list[Recipe], days: int = 7,
                  seed: int = 0, slots: list[str] | None = None) -> Plan:
    slots = slots or ["breakfast", "lunch", "dinner"]
    rng = random.Random(seed)
    by_id = {r.id: r for r in recipes}
    plan_days: list[PlanDay] = []
    reasons: list[Reason] = []
    recent: dict[str, list[str]] = {s: [] for s in slots}  # slot -> recent recipe ids

    for d in range(days):
        weekday = WEEK[d % 7]
        nonveg_allowed = weekday in household.nonveg_days
        leave_day = weekday in household.cook.leave_days
        fasting = [m for m in household.members if _is_fasting(m, weekday)]
        base_members = [m for m in household.members if m not in fasting]
        if not base_members:
            base_members = household.members  # all fasting: base itself must be vrat
            must_be_fasting = True
        else:
            must_be_fasting = False
        day_meals: list[PlannedMeal] = []
        used_today: set[str] = set()

        for slot in slots:
            pool = [r for r in recipes if slot in r.meal_types
                    and (must_be_fasting or "fasting" not in r.tags)]
            if must_be_fasting:
                pool = [r for r in pool if "fasting" in r.tags]
            if leave_day:
                pool = [r for r in pool if r.effort == "low"]
            pool = [r for r in pool if r.id not in used_today]
            reuse_note = ""
            if not pool:
                # last resort: tiny pool (e.g. vrat dinners) — allow same-day repeat
                pool = [r for r in recipes
                        if slot in r.meal_types
                        and (not must_be_fasting or "fasting" in r.tags)
                        and (not leave_day or r.effort == "low")]
                reuse_note = "small pool — same-day repeat allowed"
            window = [r for r in pool if r.id not in recent[slot][-REPEAT_WINDOW:]]
            if not window:
                window = [r for r in pool if r.id not in recent[slot][-1:]] or pool
            window.sort(key=lambda r: r.id)

            best: Recipe | None = None
            best_key: tuple = (0,)
            best_adaps: list[Adaptation] = []
            best_conflict = ""
            best_why: list[str] = []
            for r in window:
                st = _status(r, base_members, weekday, nonveg_allowed)
                excluded = [m for m in base_members if st[m.name]]
                adapts: list[Adaptation] = []
                separate: list[Member] = []
                for m in excluded:
                    a = propose_adaptation(r, m, st[m.name])
                    (adapts if a else separate).append(a if a else m)  # type: ignore
                force_nv = getattr(household, "nonveg_primary", False)
                sc, why = _score(r, base_members, recent[slot], leave_day,
                                 household.cook.skill, rng, force_nv_primary=force_nv)
                sc -= 2.0 * len(separate)  # separate dishes cost effort
                # fasting members always get their own vrat plate, preferring
                # real meals (breakfast/lunch/dinner-tagged) over snacks
                fasting_notes: list[str] = []
                if fasting and not must_be_fasting:
                    fast_all = [r for r in recipes if "fasting" in r.tags]
                    meal_like = [r for r in fast_all
                                 if set(r.meal_types) & {"breakfast", "lunch", "dinner"}]
                    for fm in fasting:
                        fd = _best_for(meal_like, [fm], weekday, nonveg_allowed, None,
                                       recent[slot], leave_day, household.cook.skill, rng)
                        if fd is None:
                            fd = _best_for(fast_all, [fm], weekday, nonveg_allowed, None,
                                           recent[slot], leave_day, household.cook.skill, rng)
                        if fd is None:
                            sc -= 10.0
                            fasting_notes.append(f"CONFLICT: no vrat dish in KB for {fm.name}")
                        else:
                            adapts.append(Adaptation(
                                member=fm.name,
                                change=f"separate fasting plate: {fd.name}",
                                note=f"vrat day | dish_id:{fd.id}"))
                            fasting_notes.append(f"vrat plate for {fm.name}: {fd.name}")
                for m in separate:
                    alt = _best_for([r for r in recipes if "fasting" not in r.tags],
                                    [m], weekday, nonveg_allowed, slot,
                                    recent[slot], leave_day, household.cook.skill, rng)
                    if alt is None:
                        sc -= 10.0
                        adapts.append(Adaptation(member=m.name,
                                                 change="CONFLICT: no safe dish in KB",
                                                 note="needs human decision"))
                    else:
                        adapts.append(Adaptation(member=m.name,
                                                 change=f"separate dish: {alt.name}",
                                                 note=f"base {r.name} unsafe ({st[m.name]})"
                                                      f" | dish_id:{alt.id}"))
                key = (round(sc, 4), -len(separate))
                if best is None or key > best_key:
                    best, best_key = r, key
                    best_adaps = adapts
                    best_why = why + fasting_notes + ([reuse_note] if reuse_note else [])
                    hard = [a for a in adapts if a.change.startswith("CONFLICT")]
                    best_conflict = "; ".join(a.change for a in hard)
            assert best is not None, f"empty recipe pool for {slot}"
            # weekend nonveg: veg base for the family + separate nonveg side
            # for nonveg members (matches real joint-family cooking)
            nv_members = [m for m in base_members if m.diet == "nonveg"]
            best_is_nv = bool(set(best.allergens) & {"chicken", "fish"}
                               or "nonveg" in best.tags)
            if nonveg_allowed and nv_members and not best_is_nv and slot in ("lunch", "dinner"):
                nv_pool = [r for r in recipes
                           if slot in r.meal_types and "nonveg" in r.tags and r.id not in used_today]
                if not nv_pool:
                    nv_pool = [r for r in recipes
                               if slot in r.meal_types and "nonveg" in r.tags]
                nv = _best_for(nv_pool, nv_members, weekday, True, slot,
                               recent[slot], leave_day, household.cook.skill, rng)
                if nv is not None:
                    side_label = "weekend nonveg side" if weekday in ("Sat", "Sun") else "nonveg side"
                    for m in nv_members:
                        best_adaps.append(Adaptation(
                            member=m.name,
                            change=f"{side_label}: {nv.name} (also eats base)",
                            note=f"extra separate dish | dish_id:{nv.id}"))
                    best_why.append(f"{side_label} for "
                                    f"{','.join(m.name for m in nv_members)}: {nv.name}")
                    used_today.add(nv.id)
                    recent[slot].append(nv.id)
            guests_n = 0
            if household.guests and weekday in household.guests.get("days", []):
                guests_n = int(household.guests.get("count", 0))
            servings = len(household.members) + guests_n
            day_meals.append(PlannedMeal(
                slot=slot, recipe_id=best.id, dish=best.name, servings=servings,
                adaptations=best_adaps, prep_tasks=_prep_tasks(best, d),
                conflict=best_conflict))
            reasons.append(Reason(day_index=d, slot=slot, dish=best.name, why=best_why,
                                  adapted_for=[a.member for a in best_adaps]))
            recent[slot].append(best.id)
            used_today.add(best.id)

        # swap pass: cap daily effort; prefer fewer distinct ingredients
        effort = sum(EFFORT_RANK[by_id[m.recipe_id].effort] for m in day_meals)
        if effort > MAX_EFFORT_PER_DAY:
            cands = sorted(day_meals, key=lambda m: -EFFORT_RANK[by_id[m.recipe_id].effort])
            for m in cands:
                if EFFORT_RANK[by_id[m.recipe_id].effort] == 0:
                    continue
                alt = _best_for(
                    [r for r in recipes if m.slot in r.meal_types and r.effort == "low"
                     and r.id not in used_today and r.id != m.recipe_id],
                    base_members, weekday, nonveg_allowed, m.slot,
                    [x for x in recent[m.slot] if x != m.recipe_id],
                    leave_day, household.cook.skill, rng)
                if alt is None:
                    continue
                old = by_id[m.recipe_id]
                why_swap = (f"swap pass: {old.name} ({old.effort}) -> "
                            f"{alt.name} (low) to cap day effort {effort}")
                m.recipe_id, m.dish = alt.id, alt.name
                m.prep_tasks = _prep_tasks(alt, d)
                used_today.discard(old.id)
                used_today.add(alt.id)
                for rs in reasons:
                    if rs.day_index == d and rs.slot == m.slot:
                        rs.dish = alt.name
                        rs.why.append(why_swap)
                effort = sum(EFFORT_RANK[by_id[x.recipe_id].effort] for x in day_meals)
                if effort <= MAX_EFFORT_PER_DAY:
                    break
        plan_days.append(PlanDay(day_index=d, weekday=weekday, meals=day_meals))
    return Plan(days=plan_days, reasons=reasons, seed=seed)
