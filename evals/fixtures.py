"""Sample households for planner tests + demos. Messy, real, Indian."""
from __future__ import annotations

from app.engine.models import CookProfile, Household, Member


def sharma_joint() -> Household:
    """Joint family: Jain dadi (fasts Thu), diabetic papa, toddler, teen nonveg weekends."""
    return Household(
        members=[
            Member(name="Dadi", age_group="senior", diet="jain", fasting_days=["Thu"]),
            Member(name="Papa", age_group="adult", diet="veg", health_notes=["low_sugar"]),
            Member(name="Mummy", age_group="adult", diet="veg", dislikes=["baingan"]),
            Member(name="Beta", age_group="teen", diet="nonveg"),
            Member(name="Chhotu", age_group="toddler", diet="veg", health_notes=["soft_food"]),
        ],
        budget_inr=6000,
        cook=CookProfile(language="Hinglish", skill="medium",
                         equipment=["pressure_cooker", "mixer"], leave_days=["Thu"]),
        nonveg_days=["Sat", "Sun"],
    )


def sen_family() -> Household:
    """Bengali family: tight budget, peanut-allergic child, Baba nonveg Sundays only."""
    return Household(
        members=[
            Member(name="Baba", age_group="adult", diet="nonveg"),
            Member(name="Ma", age_group="adult", diet="veg"),
            Member(name="Chinki", age_group="child", diet="veg", allergies=["peanut"]),
        ],
        budget_inr=3500,
        cook=CookProfile(language="Bengali+Hinglish", skill="basic",
                         equipment=["pressure_cooker"], leave_days=[]),
        nonveg_days=["Sun"],
    )


def patel_navratri() -> Household:
    """Gujarati family in Navratri week: two fasting, one Jain senior, Friday guests."""
    return Household(
        members=[
            Member(name="Kaka", age_group="adult", diet="veg", fasting_days=["Mon", "Thu"]),
            Member(name="Kaki", age_group="adult", diet="veg", fasting_days=["Mon", "Thu"]),
            Member(name="Diku", age_group="teen", diet="veg"),
            Member(name="Ba", age_group="senior", diet="jain", fasting_days=["Mon"]),
        ],
        budget_inr=8000,
        cook=CookProfile(language="Hinglish", skill="medium",
                         equipment=["pressure_cooker", "mixer"], leave_days=[]),
        nonveg_days=[],
        guests={"count": 4, "days": ["Fri"]},
    )
