"""M1 demo: print Sharma 7-day plan + reasons + Thursday detail."""
import sys
sys.path.insert(0, ".")
from evals.fixtures import sharma_joint  # noqa: E402
from app.engine.planner import generate_plan, load_recipes

R = load_recipes()
p = generate_plan(sharma_joint(), R, seed=42)
for d in p.days:
    parts = []
    for m in d.meals:
        s = f"{m.slot}:{m.dish} n={m.servings}"
        if m.adaptations:
            s += " +adapt[" + ",".join(a.member for a in m.adaptations) + "]"
        parts.append(s)
    print(d.weekday, "|", " / ".join(parts))
print("--- reasons (day 0) ---")
for rs in p.reasons[:3]:
    print(rs.slot, rs.dish, "=>", rs.why, "| adapted:", rs.adapted_for)
print("--- Thu detail (fast + cook leave) ---")
th = [d for d in p.days if d.weekday == "Thu"][0]
for m in th.meals:
    print(m.slot, m.dish, "| prep:", [t.task for t in m.prep_tasks],
          "| adap:", [(a.member, a.change[:70]) for a in m.adaptations])
