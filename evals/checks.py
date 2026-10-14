"""Deterministic eval checks (PRIMARY signal — free, repeatable).
Each check: (passed: bool, detail: str). No LLM involved."""
from __future__ import annotations

from app.engine.constraints import member_violations
from app.engine.groceries import aggregate_needs, round_to_packs, subtract_pantry
from app.engine.instamart_mock import cart_total
from app.engine.planner import REPEAT_WINDOW


def c_zero_hard_violations(st, by_id) -> tuple[bool, str]:
    bad = []
    for day in st.plan.days:
        nv = day.weekday in st.household.nonveg_days
        for m in day.meals:
            r = by_id[m.recipe_id]
            adapted = {a.member for a in m.adaptations}
            for mem in st.household.members:
                v = member_violations(r, mem, day.weekday, nv, day.weekday in mem.fasting_days)
                if v and mem.name not in adapted:
                    bad.append(f"{day.weekday} {m.slot} {r.id}: {mem.name}{v}")
    return (len(bad) == 0, f"{len(bad)} silent violations" + (f": {bad[:3]}" if bad else ""))


def c_no_conflicts(st, _by_id) -> tuple[bool, str]:
    conf = [f"d{d.day_index}{m.slot}" for d in st.plan.days for m in d.meals if m.conflict]
    return (not conf, f"conflicts: {conf}" if conf else "no CONFLICTs")


def c_qty_scaling(st, by_id) -> tuple[bool, str]:
    for day in st.plan.days:
        extra = len(st.household.guests.get("days", [])) and day.weekday in st.household.guests.get("days", [])
        want = len(st.household.members) + (int(st.household.guests.get("count", 0)) if extra else 0)
        for m in day.meals:
            # disruptions may legitimately raise servings; never below headcount
            if not (want <= m.servings <= want + 10):
                return False, f"{day.weekday} {m.slot}: {m.servings} outside [{want},{want + 10}]"
    return True, "servings cover headcount incl. guests"


def c_ingredients_covered(st, by_id) -> tuple[bool, str]:
    needs = aggregate_needs(st.plan, by_id)
    net = subtract_pantry(needs, st.household.pantry)
    from app.engine.instamart_mock import load_catalog
    lines, uncovered = round_to_packs(net, load_catalog())
    ok = not uncovered and set(net) == {ln["item"] for ln in lines}
    return ok, f"uncovered: {uncovered}" if uncovered else f"{len(lines)} lines cover all"


def c_no_repeats(st, _by_id) -> tuple[bool, str]:
    swapped = {(r.day_index, r.slot) for r in st.plan.reasons if any("user swap" in w for w in r.why)}
    for slot in ("breakfast", "lunch", "dinner"):
        seq = [(d.day_index, m.recipe_id) for d in st.plan.days for m in d.meals if m.slot == slot]
        # user-forced placements neither trigger nor populate the window
        # (known limit: swap does not replan neighbors — see M6 report)
        for i, (di, rid) in enumerate(seq):
            if (di, slot) in swapped:
                continue  # explicit user choice overrules variety, traceably
            window = [r for j, (_, r) in enumerate(seq[max(0, i - REPEAT_WINDOW):i])
                      if (seq[max(0, i - REPEAT_WINDOW) + j][0], slot) not in swapped]
            if rid in window:
                return False, f"{slot}: {rid} repeats in window"
    return True, "repeat window clean"


def c_prep_feasible(st, by_id) -> tuple[bool, str]:
    for day in st.plan.days:
        for m in day.meals:
            if by_id[m.recipe_id].needs_advance_prep and not m.prep_tasks:
                return False, f"{m.recipe_id} missing prep tasks"
        if day.weekday in st.household.cook.leave_days:
            bad = [m.dish for m in day.meals if by_id[m.recipe_id].effort != "low"]
            if bad:
                return False, f"leave-day {day.weekday} has non-low effort: {bad}"
    return True, "prep tasks + leave-day effort ok"


def c_cart_total(st, _by_id) -> tuple[bool, str]:
    ok = abs(cart_total(st.cart) - sum(ln["line_total"] for ln in st.cart)) < 1e-6
    return ok, f"total Rs.{cart_total(st.cart)} == sum lines" if ok else "total mismatch"


def c_confirm_gated(st, _by_id) -> tuple[bool, str]:
    from app.agent import tools as T
    r = T.dispatch(st, "place_order", {"confirm": True})
    ok = (not r["ok"]) and ("confirm" in r.get("error", "").lower() or r.get("need_confirm"))
    return ok, "unconfirmed order refused" if ok else f"gate broken: {r}"


def c_stockout_surfaced(st, _by_id) -> tuple[bool, str]:
    ok = bool(st.missing) or any(ln.get("substituted") for ln in st.cart)
    return ok, f"missing={st.missing}" if ok else "no stock-out in this run"


def c_budget_reported(st, _by_id) -> tuple[bool, str]:
    if st.household.budget_inr is None:
        return False, "no budget set"
    over = st.total - st.household.budget_inr
    return True, f"total Rs.{st.total} vs budget Rs.{st.household.budget_inr} ({'OVER' if over > 0 else 'within'})"


def c_allergy_separate(st, _by_id, params=None) -> tuple[bool, str]:
    for m in st.household.members:
        if not m.allergies:
            continue
        for d in st.plan.days:
            for meal in d.meals:
                for a in meal.adaptations:
                    if a.member == m.name and "separate" not in a.change and "CONFLICT" not in a.change:
                        return False, f"{m.name} got portion fix: {a.change}"
    return True, "allergy members always separate"


def c_weekend_side(st, _by_id, params=None) -> tuple[bool, str]:
    p = params or {}
    member, days = p.get("member", "Beta"), p.get("days", ["Sat", "Sun"])
    hits = [1 for d in st.plan.days if d.weekday in days for m in d.meals
            if m.slot in ("lunch", "dinner") for a in m.adaptations
            if a.member == member and "weekend nonveg side" in a.change]
    return (len(hits) > 0, f"{len(hits)} weekend sides for {member}")


def c_fasting_plates(st, _by_id, params=None) -> tuple[bool, str]:
    p = params or {}
    members, weekdays = p.get("members", []), p.get("weekdays", [])
    for d in st.plan.days:
        if d.weekday not in weekdays:
            continue
        for meal in d.meals:
            adapted = {a.member for a in meal.adaptations}
            for mem in members:
                if mem not in adapted:
                    return False, f"{d.weekday} {meal.slot}: no plate for {mem}"
    return True, f"vrat plates ok {weekdays}"


def c_soft_cover(st, by_id, params=None) -> tuple[bool, str]:
    p = params or {}
    need, tag, min_frac = p.get("need", "low_sugar"), p.get("tag", "diabetic_ok"), float(p.get("min_frac", 0.3))
    who = [m.name for m in st.household.members if need in m.health_notes]
    if not who:
        return True, "nobody needs it"
    dish_mem = [(d, m) for d in st.plan.days for m in d.meals]
    frac = sum(1 for _d, m in dish_mem if tag in by_id[m.recipe_id].tags) / len(dish_mem)
    return frac >= min_frac, f"{tag} in {frac:.0%} of meals (need {min_frac:.0%})"


def c_swap_applied(st, _by_id, params=None) -> tuple[bool, str]:
    p = params or {}
    d = next((x for x in st.plan.days if x.weekday == p.get("weekday")), None)
    if d is None:
        return False, "day missing"
    m = next((x for x in d.meals if x.slot == p.get("slot")), None)
    ok = m is not None and m.recipe_id == p.get("recipe_id")
    return ok, f"{p.get('weekday')} {p.get('slot')} = {m.recipe_id if m else '?'}"


def c_plan_adapted(st, _by_id, params=None) -> tuple[bool, str]:
    p = params or {}
    before = p.get("before")
    if not before or st.plan is None:
        return False, "no before-snapshot"
    now = st.plan.model_dump_json()
    if now == before and not st.shortfalls:
        return False, "disruption changed nothing"
    return True, "plan adapted or shortfall queued"


def c_recovery(st, _by_id, params=None) -> tuple[bool, str]:
    p = params or {}
    replies = p.get("replies", [])
    if p.get("expect_budget") is not None and st.household.budget_inr != p["expect_budget"]:
        return False, f"budget {st.household.budget_inr} != {p['expect_budget']}"
    if p.get("expect_plan_intact") and st.plan is None:
        return False, "plan wiped by correction"
    ack = any(any(w in r for w in ("Theek", "samajh", "note kar")) for r in replies)
    return ack, "recovery acknowledged" if ack else "no acknowledgement"


CHECKS = {
    "zero_hard_violations": c_zero_hard_violations,
    "no_conflicts": c_no_conflicts,
    "qty_scaling": c_qty_scaling,
    "ingredients_covered": c_ingredients_covered,
    "no_repeats": c_no_repeats,
    "prep_feasible": c_prep_feasible,
    "cart_total": c_cart_total,
    "confirm_gated": c_confirm_gated,
    "stockout_surfaced": c_stockout_surfaced,
    "budget_reported": c_budget_reported,
    "allergy_separate": c_allergy_separate,
    "weekend_side": c_weekend_side,
    "fasting_plates": c_fasting_plates,
    "soft_cover": c_soft_cover,
    "swap_applied": c_swap_applied,
    "recovery": c_recovery,
    "plan_adapted": c_plan_adapted,
}
ENGINE_DEFAULT = ["zero_hard_violations", "no_conflicts", "qty_scaling",
                  "ingredients_covered", "no_repeats", "prep_feasible",
                  "cart_total", "budget_reported"]
