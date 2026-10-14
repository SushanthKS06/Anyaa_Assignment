"""M4 scripted cook day: brief, 3 disruptions (missing item, guests,
equipment), cook log + feedback, evening lookahead. Saves transcript.
Run: python scripts/scripted_cookday.py"""
import sys
sys.path.insert(0, ".")

from app.agent.orchestrator import OrchestratorState  # noqa: E402
from app.agent.personas import AGENT_NAME  # noqa: E402
from app.engine.planner import generate_plan  # noqa: E402
from evals.fixtures import sharma_joint  # noqa: E402

st = OrchestratorState(hid="hh-scripted-m4")
st.household = sharma_joint()
st.plan = generate_plan(st.household, st.recipes, seed=42)
st.persist()

# deterministic missing item: first fresh item used on Monday
mon = next(d for d in st.plan.days if d.weekday == "Mon")
used = [ing.item for m in mon.meals
        for ing in st.by_id[m.recipe_id].ingredients]
missing_item = next(i for i in used if i in ("tomato", "onion", "potato", "lemon"))

TURNS = [
    "/cook",
    "aaj ka brief batao",
    f"{missing_item} khatm ho gaya hai",
    "4 mehman aa rahe hain dinner pe",
    "cooker kharab ho gaya hai",
    "lunch bana diya, namak thoda zyada tha",
    "kal ki taiyari batao",
]
for t in TURNS:
    print(f"Cook: {t}")
    print(f"{AGENT_NAME}: {st.handle_user(t)}")
    print("-" * 70)
jl, md = st.save_transcript("logs/transcript_m4")
print(f"saved {jl} + {md}")
print(f"taste_notes={st.taste_notes} shortfalls={st.shortfalls}")
