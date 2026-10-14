"""Tests for non-veg meal plan generation, constraint extraction, and tri-lingual presentation."""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

from app.agent.extract import extract, extract_mock
from app.agent.orchestrator import OrchestratorState
from app.engine.models import Household, HouseholdConstraints, Member
from app.engine.planner import generate_plan, load_recipes


def test_extract_mock_nonveg_tamil() -> None:
    text = "நாங்கள் வெஜிடேரியன் அண்ட் நான் வெஜிடேரியன் ரெண்டுமே சாப்பிடுவோம்"
    c = extract_mock(text)
    assert any(m.diet == "nonveg" for m in c.members), "Must extract nonveg diet"
    assert len(c.nonveg_days) > 0, "Must default nonveg_days when family eats nonveg"


def test_extract_mock_nonveg_english() -> None:
    text = "We are 2 adults, both eat non-veg. Budget is 3000."
    c = extract_mock(text)
    assert any(m.diet == "nonveg" for m in c.members)
    assert len(c.nonveg_days) > 0


def test_extract_mock_nonveg_specific_days() -> None:
    text = "Beta eats nonveg on Wednesday and Sunday"
    c = extract_mock(text)
    assert "Wed" in c.nonveg_days and "Sun" in c.nonveg_days
    assert any(m.name == "Beta" and m.diet == "nonveg" for m in c.members)


def test_planner_all_nonveg_household() -> None:
    recipes = load_recipes()
    hh = Household(
        members=[Member(name="Me", diet="nonveg")],
        nonveg_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    )
    plan = generate_plan(hh, recipes, days=3)
    meals = [m.dish for d in plan.days for m in d.meals]
    assert any("Chicken" in m or "Fish" in m or "Egg" in m or "Macher" in m for m in meals), \
        "All-nonveg household must have non-veg dishes as main meals"


def test_orchestrator_nonveg_tamil_flow() -> None:
    o = OrchestratorState(hid="hh-test-nv-ta")
    o.handle_user("வீட்ல நாலு பேருக்கும் நான் அப்பா அம்மா ஒரு குழந்தைக்கு ரெண்டு வயசு ஆகுது குழந்தைக்கு சாஃப்ட்டான ஃபுட்ஸ் தான் தரணும் எனக்கு கேரட்டில் அலர்ஜி இருக்குது நாங்கள் வெஜிடேரியன் அண்ட் நான் வெஜிடேரியன் ரெண்டுமே சாப்பிடுவோம்")
    r2 = o.handle_user("₹5000 வச்சுக்கோ. அஞ்சு நாளுக்கான மீன்பிரிப் பிளான்")
    assert o.plan is not None
    assert len(o.household.nonveg_days) > 0
    # Check that non-veg meals or sides exist in the plan
    all_dishes = [m.dish for d in o.plan.days for m in d.meals]
    all_adaps = [a.change for d in o.plan.days for m in d.meals for a in m.adaptations]
    has_nonveg = any("Chicken" in d or "Macher" in d or "Egg" in d for d in all_dishes) or \
                 any("Chicken" in a or "Macher" in a or "Egg" in a for a in all_adaps)
    assert has_nonveg, "Plan must contain non-veg dishes or sides"


def test_orchestrator_more_regex_tamil() -> None:
    o = OrchestratorState(hid="hh-test-more-ta")
    o.handle_user("வீட்டில் 2 பேர், அசைவம் சாப்பிடுவோம்")
    o.handle_user("₹4000 பட்ஜெட், 5 நாள் உணவு திட்டம்")
    assert o.plan is not None
    r3 = o.handle_user("அடுத்து")
    assert any(k in r3 for k in ["திங்கள்", "செவ்வாய்", "புதன்", "வியாழன்", "வெள்ளி", "காலை", "மதியம்", "இரவு"]), \
        "Prompting 'அடுத்து' in Tamil must show subsequent days without repeating intake"


def test_mixed_household_nonveg_primary() -> None:
    hh = Household(
        members=[
            Member(name="Me", diet="nonveg"),
            Member(name="Father", diet="nonveg"),
            Member(name="Mother", diet="nonveg"),
            Member(name="Child", diet="veg", age_group="toddler"),
        ],
        nonveg_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    )
    plan = generate_plan(hh, load_recipes(), days=7)
    main_dishes = [m.dish for d in plan.days for m in d.meals]
    # Check that non-veg dishes are scheduled as primary m.dish
    nv_mains = [d for d in main_dishes if any(nv in d for nv in ["Chicken", "Macher", "Egg"])]
    assert len(nv_mains) >= 5, f"Majority non-veg household must have non-veg main dishes (got {len(nv_mains)}: {nv_mains})"
    # Check that Child receives a separate veg adaptation
    child_adaps = [a.change for d in plan.days for m in d.meals for a in m.adaptations if a.member == "Child"]
    assert any("separate dish" in a for a in child_adaps), "Vegetarian toddler must receive separate safe veg dish"


def test_orchestrator_regenerate_to_nonveg() -> None:
    o = OrchestratorState(hid="hh-test-regen-nv")
    # Start with a mixed household
    o.handle_user("There are 4 of us: Me, Father, Mother and 2-year-old child. Budget 5000 for 7 days.")
    assert o.plan is not None
    # User requests the plan to be in non-veg
    rep = o.handle_user("the complete meal plan is in veg if i say the plan to be in non veg it should be in non veg")
    assert o.plan is not None
    assert len(o.household.nonveg_days) == 7
    assert o.household.nonveg_primary is True
    main_dishes = [m.dish for d in o.plan.days for m in d.meals]
    nv_mains = [d for d in main_dishes if any(nv in d for nv in ["Chicken", "Macher", "Egg"])]
    assert len(nv_mains) >= 5, f"Regenerated plan must feature non-veg main dishes, got: {nv_mains}"
