"""SIMULATED WhatsApp. Formats the grocery list as a chat-style message.
Rendered in the cockpit panel (M5) and returned as text for tests/cli.
Real delivery via Twilio is explicitly out of scope unless M7 says otherwise."""
from __future__ import annotations

SIMULATED = True


def render_whatsapp(household_name: str, days: int, lines: list[dict],
                    total: float, budget: int | None,
                    missing: list[str], uncovered: list[str]) -> str:
    out = [f"*SIMULATED WhatsApp msg — Grocery List ({household_name}, {days} days)*", ""]
    by_cat: dict[str, list[dict]] = {}
    for ln in lines:
        by_cat.setdefault(ln["category"], []).append(ln)
    for cat in sorted(by_cat):
        out.append(f"*{cat}*")
        for ln in sorted(by_cat[cat], key=lambda x: x["item"]):
            sub = f" (sub for {ln['substituted']['from']})" if ln.get("substituted") else ""
            out.append(f"- {ln['item']}: {ln['packs']} pack x "
                       f"{ln['pack_qty']}{ln['pack_unit']} = Rs.{ln['line_total']}{sub}")
        out.append("")
    out.append(f"*Estimated total: Rs.{total}*"
               + (f" (budget Rs.{budget}, {'OVER by Rs.' + str(round(total - budget, 2)) if total > budget else 'within budget'})" if budget else ""))
    if missing:
        out.append(f"Out of stock (will pick next time): {', '.join(sorted(missing))}")
    if uncovered:
        out.append(f"Not on Instamart (buy locally): {', '.join(sorted(uncovered))}")
    out.append("_SIMULATED — no message was actually sent_")
    return "\n".join(out)
