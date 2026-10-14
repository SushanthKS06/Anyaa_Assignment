"""Unit and integration tests for Cook Mode recipe steps, items/quantities, and tri-lingual strictness."""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

from app.agent.orchestrator import OrchestratorState
from app.engine.planner import load_recipes
from app.engine.recipe_steps import format_recipe_instructions, get_recipe_steps_en, get_recipe_steps_ta, get_recipe_steps_hi

RECIPES = {r.id: r for r in load_recipes()}


def test_recipe_steps_formatter_english() -> None:
    rec = RECIPES["upma"]
    out = format_recipe_instructions(rec, servings=4, lang="en-IN")
    assert "Vegetable Upma" in out
    assert "Items Used & Exact Quantities:" in out
    assert "Suji: 200 g" in out
    assert "Step-by-Step Cooking Process:" in out
    assert "Step 1:" in out
    assert "Gluten-free" in out


def test_recipe_steps_formatter_tamil() -> None:
    rec = RECIPES["poha"]
    out = format_recipe_instructions(rec, servings=4, lang="ta-IN")
    assert "Kanda Poha" in out
    assert "தேவையான பொருட்கள் மற்றும் அளவுகள்" in out
    assert "அவல் (Poha): 200 g" in out
    assert "வெங்காயம் (Onion): 120 g" in out
    assert "செய்முறை படி படியாக" in out
    assert "படி 1:" in out


def test_recipe_steps_formatter_hindi() -> None:
    rec = RECIPES["poha"]
    out = format_recipe_instructions(rec, servings=4, lang="hi-IN")
    assert "Kanda Poha" in out
    assert "आवश्यक सामग्री और मात्रा" in out
    assert "पोहा (Poha): 200 g" in out
    assert "पकाने की विधि क्रमवार" in out
    assert "स्टेप 1:" in out or "कदम 1:" in out


def test_cook_mode_no_household_intake() -> None:
    st = OrchestratorState(hid="test-cook-no-intake")
    st.mode = "cook"
    # Greet
    r1 = st.handle_user("Hello")
    assert "who all are in your family" not in r1.lower()
    assert "budget" not in r1.lower()
    assert "cook mode" in r1.lower() or "cooking" in r1.lower()


def test_cook_mode_recipe_request_english() -> None:
    st = OrchestratorState(hid="test-cook-recipe-en")
    st.mode = "cook"
    rep = st.handle_user("give me step by step instructions for vegetable upma with items used and quantity")
    assert "upma" in rep.lower()
    assert "suji" in rep.lower()
    assert "step" in rep.lower() or "1" in rep


def test_cook_mode_recipe_request_tamil() -> None:
    st = OrchestratorState(hid="test-cook-recipe-ta")
    st.mode = "cook"
    rep = st.handle_user("கண்டா போஹா செய்முறை படி படியா சொல்லு, என்னென்ன பொருட்கள் எவ்வளோ அளவுன்னு சொல்லு")
    assert "அவல்" in rep or "போஹா" in rep or "poha" in rep.lower()
    assert "படி" in rep or "பொருட்கள்" in rep


def test_no_budget_repeat_loop_tamil() -> None:
    st = OrchestratorState(hid="test-no-repeat")
    t1 = st.handle_user("வணக்கம்.")
    t2 = st.handle_user("வீட்டில் நாலு பேர் இருக்கோம். ஒரு குழந்தை ரெண்டு வயசு குழந்தை ஒன்று இருக்குது. சாஃப்ட் ஃபுட் வேணும்.")
    assert st.household.members, "Members should be recorded"
    t3 = st.handle_user("₹5000 வச்சுக்கோ.")
    assert st.household.budget_inr == 5000, "Budget should be recorded as 5000"
    assert st.plan is not None, "Plan should be generated automatically after budget without repeating"
