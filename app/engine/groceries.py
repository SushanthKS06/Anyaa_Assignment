"""Grocery math. Deterministic: unit normalization, aggregation (base dishes +
separate/adaptation dishes via dish_id notes), pantry subtraction, pack
rounding, allergy-safe substitution, budget compare. LLM never touches this."""
from __future__ import annotations

import math
import re

from app.engine.models import Household, Plan, Recipe

FREE_ITEMS = {"water"}  # tap water, never shopped
# dry powders: 1 tsp ~= 5g, 1 tbsp ~= 15g (approximate, documented)
DRY_ITEMS = {
    "turmeric", "cumin", "mustard_seeds", "mustard_paste", "garam_masala",
    "whole_spices", "sambar_powder", "rasam_powder", "chana_masala",
    "rajma_masala", "chicken_masala", "pav_bhaji_masala", "misal_masala",
    "amchur", "tamarind", "ajwain", "black_pepper", "sesame_seeds",
    "cardamom", "chaat_masala", "eno", "salt", "sendha_salt", "sugar", "jaggery",
}
ITEM_ALLERGEN = {
    "peanuts": "peanut", "cashew": "tree_nut", "milk": "dairy", "curd": "dairy",
    "paneer": "dairy", "ghee": "dairy", "butter": "dairy", "cream": "dairy",
    "atta": "gluten", "maida": "gluten", "suji": "gluten", "bread": "gluten",
    "pav": "gluten", "oats": "gluten", "egg": "egg", "chicken": "chicken",
    "fish_rohu": "fish", "sesame_seeds": "sesame",
    "mustard_oil": "mustard", "mustard_paste": "mustard",
}
DISH_ID_RE = re.compile(r"dish_id:([a-z_]+)")


def to_base(qty: float, unit: str, item: str) -> tuple[float, str]:
    """(qty, unit) -> (qty_in_base, kind). kinds: g, ml, pcs."""
    if unit == "g":
        return qty, "g"
    if unit == "kg":
        return qty * 1000, "g"
    if unit == "ml":
        return qty, "ml"
    if unit == "l":
        return qty * 1000, "ml"
    if unit == "pieces":
        return qty, "pcs"
    if unit == "bunch":
        return qty, "pcs"  # treated as count of bunches
    if unit in ("tsp", "tbsp"):
        mult = 5.0 if unit == "tsp" else 15.0
        if item in DRY_ITEMS:
            return qty * mult, "g"  # approx: 1 tsp powder ~= 5g
        return qty * mult, "ml"
    if unit == "cup":
        return qty * 240, "ml"
    if unit == "pinch":
        return qty * 0.4, "g"  # approx
    raise ValueError(f"unknown unit: {unit}")


def aggregate_needs(plan: Plan, by_id: dict[str, Recipe]) -> dict[str, tuple[float, str]]:
    """Sum per-serving ingredients x servings over base + extra (dish_id) dishes."""
    needs: dict[str, list] = {}
    for day in plan.days:
        for meal in day.meals:
            dishes: list[tuple[str, int]] = [(meal.recipe_id, meal.servings)]
            extra: dict[str, int] = {}
            for a in meal.adaptations:
                m = DISH_ID_RE.search(a.note)
                if m:
                    extra[m.group(1)] = extra.get(m.group(1), 0) + 1
            for did, n in extra.items():
                if did in by_id:
                    dishes.append((did, n))
            for did, servings in dishes:
                for ing in by_id[did].ingredients:
                    if ing.item in FREE_ITEMS:
                        continue
                    q, kind = to_base(ing.qty * servings, ing.unit, ing.item)
                    if ing.item in needs:
                        assert needs[ing.item][1] == kind, f"unit kind clash: {ing.item}"
                        needs[ing.item][0] += q
                    else:
                        needs[ing.item] = [q, kind]
    return {k: (round(v[0], 2), v[1]) for k, v in needs.items()}


def subtract_pantry(needs: dict[str, tuple[float, str]],
                    pantry: dict[str, dict]) -> dict[str, tuple[float, str]]:
    net: dict[str, tuple[float, str]] = {}
    for item, (qty, kind) in needs.items():
        have = 0.0
        if item in pantry:
            try:
                hq, _hk = to_base(float(pantry[item].get("qty", 0)),
                                  str(pantry[item].get("unit", "g")), item)
                have = hq
            except (ValueError, TypeError):
                have = 0.0
        left = round(qty - have, 2)
        if left > 1e-9:
            net[item] = (left, kind)
    return net


def round_to_packs(net: dict[str, tuple[float, str]],
                   catalog: dict[str, dict]) -> tuple[list[dict], list[str]]:
    """Net needs -> cart lines. Returns (lines, uncovered_items)."""
    lines: list[dict] = []
    uncovered: list[str] = []
    for item, (qty, kind) in sorted(net.items()):
        entry = catalog.get(item)
        if entry is None:
            uncovered.append(item)
            continue
        pq, _ = to_base(float(entry["pack_qty"]), str(entry["pack_unit"]), item)
        packs = max(1, math.ceil(qty / pq - 1e-9))
        lines.append({
            "sku": entry["sku"], "item": item, "category": entry["category"],
            "need_qty": qty, "need_kind": kind,
            "pack_qty": entry["pack_qty"], "pack_unit": entry["pack_unit"],
            "packs": packs, "unit_price": entry["price_inr"],
            "line_total": packs * entry["price_inr"],
            "substituted": None,
        })
    return lines, uncovered
