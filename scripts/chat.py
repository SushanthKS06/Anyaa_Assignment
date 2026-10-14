"""CLI chat for M3 testing. Commands: /cook /home /state /cart /quit."""
import sys
sys.path.insert(0, ".")

from app.agent.orchestrator import OrchestratorState  # noqa: E402
from app.agent.personas import AGENT_NAME  # noqa: E402

st = OrchestratorState()
print(f"{AGENT_NAME}: Namaste! Main {AGENT_NAME} — tumhare ghar ka khana sambhalungi. (type /quit to exit)")
while True:
    try:
        t = input("You: ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if t == "/quit":
        break
    if t == "/state":
        print(f"  [stage={st.stage} mode={st.mode} members={[m.name for m in st.household.members]} "
              f"budget={st.household.budget_inr} plan={'yes' if st.plan else 'no'} "
              f"cart={len(st.cart)} total={st.total}]")
        continue
    if t == "/cart":
        for ln in st.cart:
            print(f"  {ln['sku']} x{ln['packs']} = Rs.{ln['line_total']}")
        continue
    print(f"{AGENT_NAME}: {st.handle_user(t)}")
st.save_transcript("logs/chat_cli")
print("saved logs/chat_cli.{jsonl,md}")
