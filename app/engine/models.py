"""Pydantic v2 domain schemas. M1: full Recipe/Household/Plan graph."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AgeGroup = Literal["toddler", "child", "teen", "adult", "senior"]
Diet = Literal["veg", "jain", "eggetarian", "nonveg"]
MealType = Literal["breakfast", "lunch", "dinner", "snack", "tiffin"]
Effort = Literal["low", "medium", "high"]
Spice = Literal["mild", "medium", "hot"]

KNOWN_UNITS = {"g", "kg", "ml", "l", "pieces", "bunch", "tsp", "tbsp", "cup", "pinch"}
KNOWN_TAGS = {"veg", "vegan", "jain", "diabetic_ok", "kid_ok", "nonveg",
              "eggetarian", "fasting", "low_oil", "tiffin_ok", "leftover_ok"}
KNOWN_ALLERGENS = {"peanut", "tree_nut", "dairy", "gluten", "egg", "fish",
                   "chicken", "sesame", "soy", "mustard", "honey"}
KNOWN_MEALS = {"breakfast", "lunch", "dinner", "snack", "tiffin"}


class Ingredient(BaseModel):
    item: str = Field(min_length=1)
    qty: float = Field(gt=0)
    unit: str = Field(min_length=1)


class Recipe(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)
    spice_level: Spice = "medium"
    prep_min: int = Field(ge=0)
    cook_min: int = Field(ge=0)
    effort: Effort = "medium"
    meal_types: list[str] = Field(min_length=1)
    needs_advance_prep: str = ""  # e.g. "soak overnight" / "" if none
    ingredients: list[Ingredient] = Field(min_length=1)  # per serving
    leftover_friendly: bool = False
    fridge_life_days: int = Field(ge=0, le=7, default=1)
    substitutions: list[str] = Field(default_factory=list)


class Member(BaseModel):
    name: str = Field(min_length=1)
    age_group: AgeGroup = "adult"
    diet: Diet = "veg"
    allergies: list[str] = Field(default_factory=list)
    health_notes: list[str] = Field(default_factory=list)  # low_sugar, low_salt, soft_food
    dislikes: list[str] = Field(default_factory=list)
    fasting_days: list[str] = Field(default_factory=list)  # weekday names / festival names


class CookProfile(BaseModel):
    language: str = "Hinglish"
    skill: Literal["basic", "medium", "expert"] = "medium"
    equipment: list[str] = Field(default_factory=list)  # e.g. ["pressure_cooker", "mixer"]
    leave_days: list[str] = Field(default_factory=list)  # weekday names
    working_hours: str = "9-6"


class Household(BaseModel):
    members: list[Member] = Field(default_factory=list)  # >=1 required at plan time, not construction
    budget_inr: int | None = Field(default=None, ge=0)
    pantry: dict[str, dict] = Field(default_factory=dict)  # item -> {qty, unit}
    cook: CookProfile = Field(default_factory=CookProfile)
    nonveg_days: list[str] = Field(default_factory=list)  # weekdays when nonveg allowed
    guests: dict = Field(default_factory=dict)  # {count, days} if any
    nonveg_primary: bool = False


class HouseholdConstraints(BaseModel):
    """Extraction target: what the LLM must produce from utterances (M0/M3)."""
    members: list[Member] = Field(default_factory=list)
    days_to_plan: int = Field(default=7, ge=1, le=14)
    budget_inr: int | None = Field(default=None, ge=0)
    nonveg_days: list[str] = Field(default_factory=list)
    fasting_context: str = ""
    nonveg_primary: bool = False


class Adaptation(BaseModel):
    member: str
    change: str  # what is different for this member
    note: str = ""


class PrepTask(BaseModel):
    task: str
    deadline: str  # e.g. "night before", "morning 7am"
    day_index: int


class PlannedMeal(BaseModel):
    slot: str  # breakfast/lunch/dinner (+ snack/tiffin optional)
    recipe_id: str
    dish: str
    servings: int = Field(ge=1)
    adaptations: list[Adaptation] = Field(default_factory=list)
    prep_tasks: list[PrepTask] = Field(default_factory=list)
    conflict: str = ""  # non-empty if hard constraints forced a split


class PlanDay(BaseModel):
    day_index: int
    weekday: str
    meals: list[PlannedMeal] = Field(default_factory=list)


class Reason(BaseModel):
    day_index: int
    slot: str
    dish: str
    why: list[str] = Field(default_factory=list)
    adapted_for: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    days: list[PlanDay] = Field(default_factory=list)
    reasons: list[Reason] = Field(default_factory=list)
    seed: int = 0


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
