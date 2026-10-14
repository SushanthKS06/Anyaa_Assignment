"""Hard-constraint engine. CODE DECIDES: allergens/diets/fasting/toddler safety.
Never silently relaxes: violations are returned, and the planner must split
(base + adaptations) or cook a separate dish. One soft-weight config dict."""
from __future__ import annotations

from app.engine.models import Household, Member, Recipe

# Strict Jain: no onion/garlic family, no root vegetables.
JAIN_BANNED_ITEMS = {
    "onion", "garlic", "potato", "carrot", "radish", "beetroot",
    "sweet_potato", "turnip", "ginger", "yam", "spring_onion",
}
MEAT_ALLERGENS = {"chicken", "fish"}
SWEET_ITEMS = {"sugar", "jaggery"}
TODDLER_BANNED_ITEMS = {"honey", "peanuts", "cashew", "almonds", "peanut"}
EFFORT_RANK = {"low": 0, "medium": 1, "high": 2}

# Single soft-scoring config. Tune here, nowhere else.
SOFT_WEIGHTS: dict[str, float] = {
    "variety": 3.0,       # avoid repeats / same ingredient two days running
    "effort_fit": 2.0,    # match cook skill + leave days
    "budget": 2.0,        # prefer cheap staples when budget set (M2 prices refine)
    "leftover": 1.0,      # bonus for leftover-friendly on busy days
    "prep_fit": 2.0,      # advance-prep feasible (no soak if cook unaware)
    "preference": 1.5,    # dislikes avoided, kid_ok/diabetic_ok fit
    "fasting_cover": 2.5,  # fasting members get a real fasting plate
    "nonveg_weekend": 2.5,  # nonveg members get their weekend dish (as side)
}


def _items(recipe: Recipe) -> set[str]:
    return {ing.item for ing in recipe.ingredients}


def _has_allergen(recipe: Recipe, allergy: str) -> bool:
    a = allergy.lower()
    if a in {x.lower() for x in recipe.allergens}:
        return True
    return any(a in item for item in _items(recipe))  # e.g. peanut in peanuts


def member_violations(
    recipe: Recipe,
    member: Member,
    weekday: str,
    nonveg_allowed: bool,
    fasting_day: bool = False,
) -> list[str]:
    """All hard-constraint violations for one member eating this dish as-is."""
    v: list[str] = []
    items = _items(recipe)
    for al in member.allergies:
        if _has_allergen(recipe, al):
            v.append(f"allergy:{al}")
    if member.diet == "veg" and ("egg" in recipe.allergens or set(recipe.allergens) & MEAT_ALLERGENS
                                 or "nonveg" in recipe.tags or "eggetarian" in recipe.tags):
        v.append("diet:veg-no-egg-meat")
    if member.diet == "eggetarian" and (set(recipe.allergens) & MEAT_ALLERGENS
                                        or ("nonveg" in recipe.tags and "egg" not in recipe.allergens)):
        v.append("diet:eggetarian-no-meat")
    if member.diet == "jain" and ("jain" not in recipe.tags or items & JAIN_BANNED_ITEMS):
        v.append("diet:jain")
    if set(recipe.allergens) & MEAT_ALLERGENS or "nonveg" in recipe.tags:
        if not nonveg_allowed:
            v.append("diet:no-nonveg-day")
    if fasting_day and "fasting" not in recipe.tags:
        v.append("fasting:needs-vrat-dish")
    if member.age_group == "toddler":
        if recipe.spice_level != "mild":
            v.append("toddler:too-spicy")
        if items & TODDLER_BANNED_ITEMS:
            v.append("toddler:unsafe-item")
    if "low_sugar" in member.health_notes and items & SWEET_ITEMS:
        v.append("health:low-sugar")
    if "soft_food" in member.health_notes and recipe.spice_level == "hot":
        v.append("health:soft-food")
    for d in member.dislikes:
        if d.lower() in recipe.name.lower() or d.lower() in items:
            v.append(f"dislike:{d}")
    return v
