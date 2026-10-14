"""M3 scripted conversation: full flow with one EDIT (swap), one CORRECTION
(budget), one STOCK-OUT (seeded), and confirm-gated ordering. Saves transcript.
Run: python scripts/scripted_convo.py"""
import sys
sys.path.insert(0, ".")

from app.agent.orchestrator import OrchestratorState  # noqa: E402
from app.agent.personas import AGENT_NAME  # noqa: E402

TURNS = [
    "Namaste",
    "Ghar me 4 log hain — Dadi Jain hain aur Thursday ko fast rakhti hain, "
    "Papa diabetic hain, Beta teen hai jo weekend pe nonveg khata hai, aur Chhotu 2 saal ka hai",
    "7 din ka plan banao, budget 6000 ka hai",
    "haan nahi wait, budget 5000 hai",                      # CORRECTION
    "Tuesday dopahar ko paneer nahi, aloo gobhi bana do",   # EDIT (swap)
    "yeh kyun choose kiya?",                                # explain last swap
    "aur",                                                  # continue plan
    "grocery list banao",                                   # STOCK-OUT surfaces here
    "order karo",                                            # attempt 1 -> asks confirm
    "haan, order karo",                                     # attempt 2 -> placed
]

st = OrchestratorState(hid="hh-scripted-m3")
for t in TURNS:
    print(f"User: {t}")
    print(f"{AGENT_NAME}: {st.handle_user(t)}")
    print("-" * 70)
jl, md = st.save_transcript("logs/transcript_m3")
print(f"saved {jl} + {md}")
