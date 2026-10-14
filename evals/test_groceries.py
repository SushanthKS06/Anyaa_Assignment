"""M2 grocery tests: unit math, pantry, packs, stock-outs, totals, WhatsApp."""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from app.engine.groceries import (  # noqa: E402
    aggregate_needs,
    round_to_packs,
    subtract_pantry,
    to_base,
)
from app.engine.instamart_mock import (  # noqa: E402
    apply_stockouts,
    cart_total,
    edit_cart,
    load_catalog,
    place_order,
)
from app.engine.models import Household, Member  # noqa: E402
from app.engine.planner import generate_plan, load_recipes  # noqa: E402
from app.engine.whatsapp_mock import render_whatsapp  # noqa: E402
from evals.fixtures import patel_navratri, sen_family, sharma_joint  # noqa: E402

CATALOG = load_catalog()
RECIPES = load_recipes()
BY_ID = {r.id: r for r in RECIPES}


def test_unit_math() -> None:
    assert to_base(1, "kg", "atta") == (1000, "g")
    assert to_base(500, "g", "atta") == (500, "g")
    assert to_base(1, "tbsp", "oil") == (15.0, "ml")  # liquid tbsp -> ml
    assert to_base(1, "tsp", "salt") == (5.0, "g")  # dry tsp -> g (approx)
    assert to_base(1, "pinch", "salt") == (0.4, "g")
    assert to_base(1, "cup", "water") == (240, "ml")
    assert to_base(2, "pieces", "egg") == (2, "pcs")
    try:
        to_base(1, "furlong", "atta")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown unit must raise")


def test_mixed_units_aggregate() -> None:
    from app.engine.models import Plan, PlanDay, PlannedMeal
    plan = Plan(days=[PlanDay(day_index=0, weekday="Mon", meals=[
        PlannedMeal(slot="lunch", recipe_id="dal_tadka", dish="x", servings=2),
        PlannedMeal(slot="dinner", recipe_id="rasam_sadam", dish="y", servings=3),
    ])], reasons=[])
    needs = aggregate_needs(plan, BY_ID)
    # ghee: dal 10ml x 2 servings; oil: rasam 5ml x 3 servings
    assert needs["ghee"] == (20.0, "ml"), needs["ghee"]
    assert needs["oil"] == (15.0, "ml"), needs["oil"]
    # cumin: 0.5tsp dry -> 2.5g per serving; 2 + 3 servings = 12.5g
    assert needs["cumin"] == (12.5, "g"), needs["cumin"]


def test_fractional_packs_round_up() -> None:
    lines, uncovered = round_to_packs({"peanuts": (600, "g")}, CATALOG)
    assert uncovered == []
    assert lines[0]["packs"] == 2 and lines[0]["line_total"] == 160  # 500g packs
    lines, _ = round_to_packs({"atta": (420, "g")}, CATALOG)
    assert lines[0]["packs"] == 1  # 5kg pack


def test_pantry_subtraction() -> None:
    needs = {"atta": (420.0, "g"), "rice": (2000.0, "g")}
    net = subtract_pantry(needs, {"atta": {"qty": 2, "unit": "kg"}})
    assert "atta" not in net  # fully covered
    assert net["rice"] == (2000.0, "g")
    net2 = subtract_pantry(needs, {"rice": {"qty": 1.5, "unit": "kg"}})
    assert net2["rice"] == (500.0, "g")  # partial
    lines, _ = round_to_packs(net2, CATALOG)
    assert lines[0]["packs"] == 1  # 500g left but 5kg pack


def test_perishable_packs_and_duplicates() -> None:
    lines, uncovered = round_to_packs(
        {"milk": (900, "ml"), "curd": (800, "g")}, CATALOG)
    assert uncovered == []
    assert {ln["item"]: ln["packs"] for ln in lines} == {"milk": 2, "curd": 2}


def test_every_plan_ingredient_covered_or_pantry() -> None:
    """Spec check: every plan ingredient lands in the grocery list or pantry."""
    for hh in (sharma_joint(), sen_family(), patel_navratri()):
        plan = generate_plan(hh, RECIPES, seed=42)
        needs = aggregate_needs(plan, BY_ID)
        net = subtract_pantry(needs, hh.pantry)
        lines, uncovered = round_to_packs(net, CATALOG)
        assert uncovered == [], f"items missing from catalog: {uncovered}"
        lined = {ln["item"] for ln in lines}
        assert set(net) == lined


def test_guests_scale_and_extras_included() -> None:
    plan = generate_plan(patel_navratri(), RECIPES, seed=42)
    needs = aggregate_needs(plan, BY_ID)
    assert "chicken" not in needs  # all-veg household, no nonveg side
    plan_s = generate_plan(sharma_joint(), RECIPES, seed=42)
    needs_s = aggregate_needs(plan_s, BY_ID)
    assert "chicken" in needs_s  # Beta's weekend side
    assert "kuttu_atta" in needs_s  # Dadi's Thursday vrat plate
    # Friday Patel servings=8 -> Friday lunch's first ingredient scaled x8
    fri = [d for d in plan.days if d.weekday == "Fri"][0]
    assert all(m.servings == 8 for m in fri.meals)
    first = BY_ID[fri.meals[1].recipe_id].ingredients[0]
    q, _kind = to_base(first.qty * 8, first.unit, first.item)
    assert needs[first.item][0] >= q - 1e-9


def test_stockout_substitution_and_allergy_safety() -> None:
    lines, _ = round_to_packs({"butter": (30, "g"), "rice": (6000, "g")}, CATALOG)
    # no allergy: butter -> ghee sub
    l2, missing = apply_stockouts([dict(ln) for ln in lines], CATALOG, seed=1,
                                  force_out=["butter-100g"])
    assert missing == []
    b = [ln for ln in l2 if ln["item"] == "butter"][0]
    assert b["substituted"] == {"from": "butter-100g", "to": "ghee-500ml"}
    # dairy allergy: ghee also dairy -> must NOT substitute -> missing
    l3, missing3 = apply_stockouts([dict(ln) for ln in lines], CATALOG, seed=1,
                                   allergies={"dairy"}, force_out=["butter-100g"])
    assert missing3 == ["butter"]
    assert all(ln["item"] != "butter" for ln in l3)


def test_cart_total_is_sum_and_edit_cart() -> None:
    lines, _ = round_to_packs({"rice": (6000, "g"), "egg": (7, "pcs")}, CATALOG)
    assert cart_total(lines) == sum(ln["line_total"] for ln in lines)
    sku = [ln for ln in lines if ln["item"] == "egg"][0]["sku"]
    e2 = edit_cart(lines, sku, 2)
    assert cart_total(e2) == cart_total(lines)  # 7pcs->2 packs was already 2
    e3 = edit_cart(lines, sku, 0)
    assert all(ln["item"] != "egg" for ln in e3)
    assert cart_total(e3) == sum(ln["line_total"] for ln in e3)


def test_place_order_shape() -> None:
    lines, _ = round_to_packs({"rice": (100, "g")}, CATALOG)
    o = place_order(lines, seed=42)
    assert o["simulated"] is True
    assert o["order_id"].startswith("SM-ORD-")
    assert 45 <= o["eta_min"] <= 90
    assert o["total_inr"] == cart_total(lines)


def test_whatsapp_renders() -> None:
    hh = sharma_joint()
    plan = generate_plan(hh, RECIPES, seed=42)
    needs = aggregate_needs(plan, BY_ID)
    lines, uncovered = round_to_packs(subtract_pantry(needs, hh.pantry), CATALOG)
    lines, missing = apply_stockouts(lines, CATALOG, seed=42)
    total = cart_total(lines)
    msg = render_whatsapp("Sharma", 7, lines, total, hh.budget_inr, missing, uncovered)
    assert "SIMULATED" in msg
    assert "*Staples*" in msg and "Estimated total" in msg
    assert f"Rs.{total}" in msg
    assert "_SIMULATED" in msg
    _ = Household, Member  # re-export guard
