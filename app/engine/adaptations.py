"""Per-member adaptations. Returns an Adaptation when a violation can be fixed
by cooking a portion differently; None when a separate dish is required.
Allergies and meat/fasting presence are NEVER adaptable — separate dish."""
from __future__ import annotations

from app.engine.models import Adaptation, Member, Recipe
from app.engine.constraints import _items  # internal helper, same package


def propose_adaptation(recipe: Recipe, member: Member, violations: list[str]) -> Adaptation | None:
    items = _items(recipe)
    # Meat/egg in the pot can never be portioned away for veg/jain members.
    if set(recipe.allergens) & {"chicken", "fish", "egg"} and member.diet in ("veg", "jain"):
        return None
    hard_separate = [v for v in violations
                     if v.startswith("allergy:") or v == "diet:veg-no-egg-meat"
                     or v == "diet:eggetarian-no-meat" or v.startswith("fasting:")
                     or v == "diet:no-nonveg-day" or v.startswith("health:low-sugar")]
    if hard_separate:
        return None
    changes: list[str] = []
    for v in violations:
        if v == "diet:jain":
            bad = sorted(items & {"onion", "garlic", "potato", "carrot", "radish",
                                  "beetroot", "ginger"})
            changes.append(f"no-onion-garlic portion cooked first ({', '.join(bad) or 'tadka'} skipped)")
        elif v == "toddler:too-spicy" or v == "health:soft-food":
            changes.append("extra-mild mashed portion, chilli on side")
        elif v == "toddler:unsafe-item":
            changes.append("nut-free portion, mashed soft")
        elif v.startswith("dislike:"):
            changes.append(f"serve deconstructed so {member.name} can skip {v.split(':', 1)[1]}")
    if not changes:
        return None
    return Adaptation(member=member.name, change="; ".join(changes),
                      note=f"from base dish {recipe.name}")
