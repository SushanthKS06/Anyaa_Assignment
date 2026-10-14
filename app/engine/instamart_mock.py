"""SIMULATED Instamart. No real API, no real money, no real delivery.
Seeded stock-outs, cart add/remove/edit, totals, ETA, fake order ids.
Everything here is labeled SIMULATED in code, logs, and UI."""
from __future__ import annotations

import json
import random

SIMULATED = True


def load_catalog(path: str = "app/data/instamart_catalog.json") -> dict[str, dict]:
    raw = json.loads(open(path, encoding="utf-8").read())
    return {e["item"]: e for e in raw}


def stockouts(catalog: dict[str, dict], seed: int, rate: float = 0.12,
              force_out: list[str] | None = None) -> set[str]:
    """Which SKUs are out of stock. Deterministic per seed; tests use force_out."""
    if force_out is not None:
        return set(force_out)
    rng = random.Random(seed)
    return {e["sku"] for e in catalog.values() if rng.random() < rate}


def household_allergens(household) -> set[str]:
    return {a.lower() for m in household.members for a in m.allergies}


def apply_stockouts(lines: list[dict], catalog: dict[str, dict], seed: int,
                    allergies: set[str] | None = None,
                    force_out: list[str] | None = None) -> tuple[list[dict], list[str]]:
    """Replace out-of-stock lines with substitutes (allergy-safe). Returns
    (updated lines, missing_items). Never substitutes into an allergen."""
    from app.engine.groceries import ITEM_ALLERGEN
    allergies = allergies or set()
    out = stockouts(catalog, seed, force_out=force_out)
    by_sku = {e["sku"]: e for e in catalog.values()}
    missing: list[str] = []
    for line in lines:
        if line["sku"] not in out:
            continue
        replaced = False
        for sub_sku in catalog[line["item"]].get("substitutes", []):
            if sub_sku in out:
                continue
            sub_item = by_sku[sub_sku]["item"]
            if ITEM_ALLERGEN.get(sub_item, "").lower() in allergies:
                continue
            line["substituted"] = {"from": line["sku"], "to": sub_sku}
            line["sku"] = sub_sku
            line["unit_price"] = by_sku[sub_sku]["price_inr"]
            line["line_total"] = line["packs"] * line["unit_price"]
            replaced = True
            break
        if not replaced:
            missing.append(line["item"])
    lines = [ln for ln in lines if ln["item"] not in missing]
    return lines, missing


def cart_total(lines: list[dict]) -> float:
    return round(sum(ln["line_total"] for ln in lines), 2)


def edit_cart(lines: list[dict], sku: str, packs: int) -> list[dict]:
    """Set pack count (0 removes). Recalculates line total."""
    out: list[dict] = []
    for ln in lines:
        if ln["sku"] == sku:
            if packs <= 0:
                continue
            ln = {**ln, "packs": packs, "line_total": packs * ln["unit_price"]}
        out.append(ln)
    return out


def place_order(lines: list[dict], seed: int) -> dict:
    """SIMULATED checkout. Returns fake order id + ETA. No payment, no network."""
    rng = random.Random(seed)
    total = cart_total(lines)
    return {
        "simulated": True,
        "order_id": f"SM-ORD-{seed:04d}-{rng.randint(1000, 9999)}",
        "eta_min": rng.randint(45, 90),
        "lines": len(lines),
        "total_inr": total,
    }
