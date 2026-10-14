"""M2 demo: Sharma 7-day plan -> groceries -> SIMULATED cart -> WhatsApp text."""
import sys
sys.path.insert(0, ".")

from app.engine.groceries import aggregate_needs, round_to_packs, subtract_pantry  # noqa: E402
from app.engine.instamart_mock import (  # noqa: E402
    apply_stockouts,
    cart_total,
    household_allergens,
    load_catalog,
    place_order,
)
from app.engine.planner import generate_plan, load_recipes  # noqa: E402
from app.engine.whatsapp_mock import render_whatsapp  # noqa: E402
from evals.fixtures import sharma_joint  # noqa: E402

hh = sharma_joint()
recipes = load_recipes()
by_id = {r.id: r for r in recipes}
catalog = load_catalog()
print(f"catalog SKUs: {len(catalog)}")
plan = generate_plan(hh, recipes, seed=42)
needs = aggregate_needs(plan, by_id)
print(f"distinct items needed: {len(needs)}")
net = subtract_pantry(needs, hh.pantry)
lines, uncovered = round_to_packs(net, catalog)
print(f"cart lines: {len(lines)} uncovered: {uncovered}")
lines, missing = apply_stockouts(lines, catalog, seed=42,
                                 allergies=household_allergens(hh))
subs = [ln for ln in lines if ln.get("substituted")]
print(f"substitutions: {len(subs)} {[ (s['item'], s['substituted']) for s in subs ]}")
print(f"missing: {missing}")
total = cart_total(lines)
print(f"TOTAL Rs.{total} vs budget Rs.{hh.budget_inr}")
order = place_order(lines, seed=42)
print(f"SIMULATED order: {order}")
print("=" * 60)
print(render_whatsapp("Sharma", 7, lines, total, hh.budget_inr, missing, uncovered))
