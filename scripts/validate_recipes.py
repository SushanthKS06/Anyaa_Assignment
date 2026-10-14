"""Recipe KB validator. Hard errors fail; soft flags print as MANUAL REVIEW list.
Run: python scripts/validate_recipes.py. This KB is NOT claimed verified."""
from __future__ import annotations

import json
import sys

sys.path.insert(0, ".")

from app.engine.models import KNOWN_ALLERGENS, KNOWN_MEALS, KNOWN_TAGS, KNOWN_UNITS, Recipe  # noqa: E402

JAIN_ROOT = {"onion", "garlic", "potato", "carrot", "radish", "beetroot",
             "sweet_potato", "turnip", "ginger", "yam"}
FASTING_FORBIDDEN = {"rice", "atta", "maida", "suji", "besan", "bread", "pav",
                     "oats", "onion", "garlic", "salt", "toor_dal", "moong_dal",
                     "masoor_dal", "chana_dal", "rajma", "kabuli_chana"}
SWEET_ITEMS = {"sugar", "jaggery"}
MEAT = {"chicken", "fish"}


def validate() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    review: list[str] = []
    raw = json.loads(open("app/data/recipes.json", encoding="utf-8").read())
    seen: set[str] = set()
    recipes: list[Recipe] = []
    for i, r in enumerate(raw):
        try:
            rec = Recipe.model_validate(r)
        except Exception as e:
            errors.append(f"[{r.get('id', i)}] schema: {e}")
            continue
        recipes.append(rec)
        if rec.id in seen:
            errors.append(f"[{rec.id}] duplicate id")
        seen.add(rec.id)
        if set(rec.tags) - KNOWN_TAGS:
            errors.append(f"[{rec.id}] unknown tags: {set(rec.tags) - KNOWN_TAGS}")
        if set(rec.allergens) - KNOWN_ALLERGENS:
            errors.append(f"[{rec.id}] unknown allergens: {set(rec.allergens) - KNOWN_ALLERGENS}")
        if set(rec.meal_types) - KNOWN_MEALS:
            errors.append(f"[{rec.id}] unknown meal_types: {set(rec.meal_types) - KNOWN_MEALS}")
        items = {ing.item for ing in rec.ingredients}
        for ing in rec.ingredients:
            if ing.unit not in KNOWN_UNITS:
                errors.append(f"[{rec.id}] unknown unit {ing.unit} for {ing.item}")
            lim = {"g": 500, "ml": 500, "pieces": 8, "tsp": 4, "tbsp": 4,
                   "cup": 3, "pinch": 3, "bunch": 2, "kg": 0.5, "l": 0.5}.get(ing.unit, 10**9)
            if not (0 < ing.qty <= lim):
                errors.append(f"[{rec.id}] implausible qty {ing.qty}{ing.unit} for {ing.item}")
        # cross-checks: hard errors
        dairy_items = {"paneer", "curd", "milk", "ghee", "butter", "cream", "cheese"}
        if items & dairy_items and "dairy" not in rec.allergens:
            errors.append(f"[{rec.id}] has dairy items {items & dairy_items} but no dairy allergen")
        if "peanuts" in items and "peanut" not in rec.allergens:
            errors.append(f"[{rec.id}] has peanuts but no peanut allergen")
        if "jain" in rec.tags and items & JAIN_ROOT:
            errors.append(f"[{rec.id}] tagged jain but contains {items & JAIN_ROOT}")
        if "fasting" in rec.tags and items & FASTING_FORBIDDEN:
            errors.append(f"[{rec.id}] tagged fasting but contains {items & FASTING_FORBIDDEN}")
        if "vegan" in rec.tags and (items & dairy_items or "egg" in items or "honey" in items):
            errors.append(f"[{rec.id}] tagged vegan but contains animal items")
        has_meat_item = any(any(m in it for m in ("chicken", "fish", "mutton", "egg"))
                            for it in items)
        if "nonveg" in rec.tags and not (has_meat_item or set(rec.allergens) & {"chicken", "fish", "egg"}):
            errors.append(f"[{rec.id}] tagged nonveg but no meat/egg")
        if (items & MEAT or has_meat_item) and "nonveg" not in rec.tags:
            errors.append(f"[{rec.id}] has meat but no nonveg tag")
        # soft: manual review
        if rec.spice_level == "hot" and "kid_ok" in rec.tags:
            review.append(f"[{rec.id}] kid_ok but HOT spice — confirm with parents")
        if "kid_ok" in rec.tags and ({"peanut", "tree_nut"} & set(rec.allergens)):
            review.append(f"[{rec.id}] kid_ok but has nuts — toddler choking/allergy risk")
        if "diabetic_ok" in rec.tags and items & SWEET_ITEMS:
            review.append(f"[{rec.id}] diabetic_ok but contains {items & SWEET_ITEMS}")
        if "diabetic_ok" in rec.tags and "potato" in items:
            review.append(f"[{rec.id}] diabetic_ok but has potato — portion caution")
        if rec.allergens and not rec.substitutions:
            review.append(f"[{rec.id}] has allergens {rec.allergens} but no substitutions listed")
        if "kid_ok" in rec.tags and any(it in SWEET_ITEMS for it in items
                                         for ing in rec.ingredients if ing.item == it and ing.qty > 15):
            review.append(f"[{rec.id}] kid_ok but sugary (>15g) — tiffin caution")
    return errors, review


def main() -> int:
    errors, review = validate()
    raw = json.loads(open("app/data/recipes.json", encoding="utf-8").read())
    print(f"recipes: {len(raw)} | errors: {len(errors)} | review flags: {len(review)}")
    for e in errors:
        print(f"  ERROR {e}")
    if review:
        print("--- MANUAL REVIEW LIST (human must confirm; KB not verified) ---")
        for r in review:
            print(f"  REVIEW {r}")
    else:
        print("--- MANUAL REVIEW LIST: none flagged (still not verified) ---")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
