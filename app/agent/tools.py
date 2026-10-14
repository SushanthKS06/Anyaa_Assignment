"""Toolbelt: strict Pydantic args, one dispatcher, one repair retry.
Tools 1-12 = household planning + order + pantry (M3). Kitchen tools
(get_daily_brief, report_disruption, log_cooked) land in M4 with kitchen.py.
Invalid args -> validation error -> one normalize-and-retry -> structured error."""
from __future__ import annotations

import re
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field, ValidationError

from app.agent.extract import DAYMAP
from app.config import CONFIG
from app.engine.adaptations import propose_adaptation
from app.engine.groceries import aggregate_needs, round_to_packs, subtract_pantry
from app.engine.instamart_mock import (
    apply_stockouts,
    cart_total,
    edit_cart,
    household_allergens,
    place_order,
)
from app.engine.models import Adaptation, Diet, Member
from app.engine.planner import _best_for, _status, generate_plan
from app.engine.whatsapp_mock import render_whatsapp

SLOTMAP = {"nashta": "breakfast", "breakfast": "breakfast", "subah": "breakfast",
           "kaalai": "breakfast", "காலை": "breakfast", "tiffin": "tiffin", "டிபன்": "tiffin",
           "dopahar": "lunch", "lunch": "lunch", "madhiyam": "lunch", "mathiyam": "lunch",
           "மதியம்": "lunch", "மத்தியம்": "lunch",
           "raat": "dinner", "dinner": "dinner", "iravu": "dinner", "இரவு": "dinner",
           "shaam": "snack", "snack": "snack", "saayandhiram": "snack", "சாயங்காலம்": "snack"}


def norm_day(s: str) -> str:
    t = s.strip().lower()
    for k, v in DAYMAP.items():
        if k in t or t == v.lower():
            return v
    cap = s.strip().capitalize()
    if cap in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"):
        return cap
    raise ValueError(f"unknown day: {s}")


def norm_slot(s: str) -> str:
    t = s.strip().lower()
    if t in SLOTMAP:
        return SLOTMAP[t]
    raise ValueError(f"unknown slot: {s}")


DISH_ALIASES: dict[str, str] = {
    # Tamil aliases
    "போஹா": "poha", "கண்டா போஹா": "poha", "பொறா": "poha", "அவல்": "poha",
    "உப்மா": "upma", "ரவா உப்மா": "upma", "உபமா": "upma",
    "இட்லி சாம்பார்": "idli_sambar", "இட்லி": "idli_sambar",
    "மசாலா தோசை": "masala_dosa", "தோசை": "masala_dosa",
    "ஆலு பரோட்டா": "aloo_paratha", "பரோட்டா": "aloo_paratha", "பராதா": "aloo_paratha",
    "பேசன் சில்லா": "besan_chilla", "கடலை மாவு சில்லா": "besan_chilla",
    "மூங் தால் சில்லா": "moong_dal_chilla", "பாசிப்பருப்பு சில்லா": "moong_dal_chilla",
    "மேத்தி தெப்லா": "methi_thepla", "தெப்லா": "methi_thepla",
    "சாபுதானா கிச்சடி": "sabudana_khichdi", "ஜவ்வரிசி கிச்சடி": "sabudana_khichdi",
    "ராஜ்மா சாவல்": "rajma_chawal", "ராஜ்மா": "rajma_chawal",
    "சென்னா மசாலா": "chana_masala", "சென்னா": "chana_masala", "சோலே": "chana_masala",
    "தால் தட்கா": "dal_tadka", "பருப்பு தட்கா": "dal_tadka",
    "பாலக் தால்": "palak_dal", "கீரை பருப்பு": "palak_dal",
    "சாம்பார் சாதம்": "sambar_sadam",
    "ரசம் சாதம்": "rasam_sadam",
    "தயிர் சாதம்": "curd_rice",
    "எலுமிச்சை சாதம்": "lemon_rice", "லெமன் ரைஸ்": "lemon_rice",
    "வெஜ் புலாவ்": "veg_pulao", "புலாவ்": "veg_pulao",
    "கதி கிச்சடி": "kadhi_khichdi",
    "மூங் கிச்சடி": "moong_khichdi", "கிச்சடி": "moong_khichdi",
    "சுரைக்காய் பருப்பு": "lauki_chana_dal",
    "ஆலு கோபி": "aloo_gobhi", "உருளை காலிஃபிளவர்": "aloo_gobhi",
    "வெண்டைக்காய் மசாலா": "bhindi_masala", "பிண்டி மசாலா": "bhindi_masala",
    "பன்னீர் பட்டர் மசாலா": "paneer_butter_masala",
    "மட்டர் பன்னீர்": "matar_paneer",
    "பன்னீர் பூர்ஜி": "paneer_bhurji", "பன்னீர் புர்ஜி": "paneer_bhurji", "பணீர் பூர்ஜி": "paneer_bhurji",
    "காளான் மசாலா": "mushroom_masala", "மஷ்ரூம் மசாலா": "mushroom_masala",
    "தால் ப்ரை": "dal_fry",
    "சிக்கன் கறி": "chicken_curry", "கோழி கறி": "chicken_curry", "சிக்கன்": "chicken_curry", "சிக்கன் குழம்பு": "chicken_curry", "கோழிக்கறி": "chicken_curry",
    "மீன் குழம்பு": "macher_jhol", "மீன்": "macher_jhol", "மீன்குழம்பு": "macher_jhol", "மீன் கறி": "macher_jhol",
    "முட்டை கறி": "egg_curry", "முட்டை": "egg_curry", "முட்டை குழம்பு": "egg_curry", "முட்டைக்குழம்பு": "egg_curry",
    "பாவ் பாஜி": "pav_bhaji",
    "டோக்லா": "dhokla", "கமன் டோக்லா": "dhokla",
    "சாண்ட்விச்": "veg_sandwich",
    "உத்தப்பம்": "uttapam", "தக்காளி உத்தப்பம்": "uttapam",
    "பனியாரம்": "appe", "அப்பே": "appe",
    "சமோசா": "samosa",
    # Hindi aliases
    "पोहा": "poha", "कांदा पोहा": "poha",
    "उपमा": "upma",
    "इडली सांबर": "idli_sambar", "इडली": "idli_sambar",
    "मसाला डोसा": "masala_dosa", "डोसा": "masala_dosa",
    "आलू पराठा": "aloo_paratha", "पराठा": "aloo_paratha",
    "बेसन चीला": "besan_chilla",
    "मूंग दाल चीला": "moong_dal_chilla",
    "मेथी थेपला": "methi_thepla", "थेपला": "methi_thepla",
    "साबूदाना खिचड़ी": "sabudana_khichdi",
    "राजमा चावल": "rajma_chawal", "राजमा": "rajma_chawal",
    "चना मसाला": "chana_masala", "छोले": "chana_masala",
    "दाल तड़का": "dal_tadka",
    "पालक दाल": "palak_dal",
    "सांभर सादम": "sambar_sadam",
    "रसम सादम": "rasam_sadam",
    "दही चावल": "curd_rice", "कर्ड राइस": "curd_rice",
    "लेमन राइस": "lemon_rice",
    "वेज पुलाव": "veg_pulao", "पुलाव": "veg_pulao",
    "कढ़ी खिचड़ी": "kadhi_khichdi",
    "मूंग खिचड़ी": "moong_khichdi", "खिचड़ी": "moong_khichdi",
    "आलू गोभी": "aloo_gobhi",
    "भिंडी मसाला": "bhindi_masala",
    "पनीर बटर मसाला": "paneer_butter_masala",
    "मटर पनीर": "matar_paneer",
    "पनीर भुर्जी": "paneer_bhurji",
    "मशरूम मसाला": "mushroom_masala",
    "दाल फ्राई": "dal_fry",
    "चिकन करी": "chicken_curry", "चिकन": "chicken_curry",
    "मछली करी": "macher_jhol", "माछेर झोल": "macher_jhol", "मछली": "macher_jhol",
    "अंडा करी": "egg_curry", "अंडा": "egg_curry", "अंडे की करी": "egg_curry",
    "पाव भाजी": "pav_bhaji",
    "ढोकला": "dhokla",
    "सैंडविच": "veg_sandwich",
    # English aliases
    "chicken curry": "chicken_curry", "chicken": "chicken_curry",
    "macher jhol": "macher_jhol", "fish curry": "macher_jhol", "fish": "macher_jhol",
    "egg curry": "egg_curry", "egg": "egg_curry",
    "उत्तपम": "uttapam",
    "अप्पे": "appe",
    "समोसा": "samosa",
}


def match_dish(text: str, by_id: dict) -> str | None:
    t = text.lower().replace("_", " ").strip()
    if not t:
        return None
    # 1. Check aliases first (sorted by descending length)
    for alias, rid in sorted(DISH_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if alias in t and rid in by_id:
            return rid
    # 2. Exact match on id or name
    for rid, r in by_id.items():
        if t == rid.replace("_", " ") or t == r.name.lower():
            return rid
    # 3. Substring match
    for rid, r in by_id.items():
        clean_rid = rid.replace("_", " ")
        clean_name = r.name.lower()
        if clean_rid in t or clean_name in t:
            return rid
        if t in clean_rid or t in clean_name:
            return rid
    # 4. Token-level match for core dish word
    words = [w for w in re.findall(r"[a-zA-Z]+", t) if len(w) > 3 and w not in ("recipe", "step", "steps", "instructions", "detail", "make", "cook")]
    for w in words:
        for rid, r in by_id.items():
            if w in rid or w in r.name.lower():
                return rid
    return None


# ---- arg schemas ----
class AddMemberArgs(BaseModel):
    member: Member


class UpdateHouseholdArgs(BaseModel):
    budget_inr: int | None = Field(default=None, ge=0)
    days_to_plan: int | None = Field(default=None, ge=1, le=14)
    nonveg_days: list[str] = Field(default_factory=list)


class SetConstraintArgs(BaseModel):
    member_name: str = Field(min_length=1)
    field: Literal["diet", "allergies", "health_notes", "dislikes", "fasting_days"]
    value: str = Field(min_length=1)


class GeneratePlanArgs(BaseModel):
    days: int | None = Field(default=None, ge=1, le=14)
    seed: int = Field(default_factory=lambda: CONFIG.planner_seed)


class SwapMealArgs(BaseModel):
    day: str
    slot: str
    new_dish: str = ""


class ExplainMealArgs(BaseModel):
    day: str
    slot: str


class BuildGroceryListArgs(BaseModel):
    seed: int = Field(default_factory=lambda: CONFIG.grocery_seed)


class EditCartArgs(BaseModel):
    sku: str = Field(min_length=1)
    packs: int = Field(ge=0)


class PlaceOrderArgs(BaseModel):
    confirm: bool = False


class UpdatePantryArgs(BaseModel):
    item: str = Field(min_length=1)
    qty: float = Field(ge=0)
    unit: str = Field(min_length=1)


class DailyBriefArgs(BaseModel):
    weekday: str = ""


class ReportDisruptionArgs(BaseModel):
    kind: Literal["missing_ingredient", "extra_guests", "equipment_broken",
                  "cook_leave", "low_energy"]
    detail: str = ""
    day: str = ""
    slot: str = ""


class LogCookedArgs(BaseModel):
    slot: str
    status: Literal["cooked", "skipped"] = "cooked"
    note: str = ""


class UndoArgs(BaseModel):
    pass


class NoArgs(BaseModel):
    pass


# ---- implementations (ctx = OrchestratorState, duck-typed) ----
def t_add_member(ctx: Any, a: AddMemberArgs) -> dict:
    names = {m.name: i for i, m in enumerate(ctx.household.members)}
    if a.member.name in names:
        ctx.household.members[names[a.member.name]] = a.member
        return {"ok": True, "updated": a.member.name}
    ctx.household.members.append(a.member)
    return {"ok": True, "added": a.member.name, "members": len(ctx.household.members)}


def t_update_household(ctx: Any, a: UpdateHouseholdArgs) -> dict:
    if a.budget_inr is not None:
        ctx.household.budget_inr = a.budget_inr
    if a.days_to_plan is not None:
        ctx.days_to_plan = a.days_to_plan
    if a.nonveg_days:
        ctx.household.nonveg_days = sorted({norm_day(d) for d in a.nonveg_days})
    return {"ok": True, "budget": ctx.household.budget_inr, "days": ctx.days_to_plan}


def t_set_constraint(ctx: Any, a: SetConstraintArgs) -> dict:
    ms = [m for m in ctx.household.members if m.name.lower() == a.member_name.lower()]
    if not ms:
        return {"ok": False, "error": f"no member named {a.member_name}"}
    m = ms[0]
    vals = [v.strip() for v in a.value.split(",") if v.strip()]
    if a.field == "diet":
        trial = m.model_copy(update={"diet": vals[0].lower()})
        Member.model_validate(trial.model_dump())  # raises before any mutation
        m.diet = trial.diet  # type: ignore
    elif a.field == "fasting_days":
        m.fasting_days = sorted({norm_day(v) for v in vals})
    else:
        setattr(m, a.field, sorted(set(getattr(m, a.field)) | set(vals)))
    ctx.plan = None  # constraints changed -> plan stale
    return {"ok": True, "member": m.name, "field": a.field, "now": getattr(m, a.field)}


def t_generate_plan(ctx: Any, a: GeneratePlanArgs) -> dict:
    if not ctx.household.members:
        return {"ok": False, "error": "koi member nahi — pehle ghar walo ke naam batao"}
    days = a.days or ctx.days_to_plan
    ctx.plan = generate_plan(ctx.household, ctx.recipes, days=days, seed=a.seed)
    ctx.presented_until = 0
    ctx.stage = "NEGOTIATE"
    ctx.persist()
    n_adapt = sum(len(m.adaptations) for d in ctx.plan.days for m in d.meals)
    conflicts = [f"d{d.day_index} {m.slot}: {m.conflict}" for d in ctx.plan.days
                 for m in d.meals if m.conflict]
    return {"ok": True, "days": days, "meals": days * 3, "adaptations": n_adapt,
            "conflicts": conflicts}


def _swap_target(ctx: Any, day: str, slot: str, want: str) -> dict:
    weekday = norm_day(day)
    meal_slot = norm_slot(slot)
    if ctx.plan is None:
        return {"ok": False, "error": "no plan yet — pehle plan banate hain"}
    days = [d for d in ctx.plan.days if d.weekday == weekday]
    if not days:
        return {"ok": False, "error": f"{weekday} plan me nahi hai"}
    pm = next((m for m in days[0].meals if m.slot == meal_slot), None)
    if pm is None:
        return {"ok": False, "error": f"{meal_slot} us din nahi hai"}
    rid = match_dish(want, ctx.by_id) if want else None
    if want and rid is None:
        return {"ok": False, "error": f"'{want}' meri list me nahi — kuch aur batao"}
    nonveg_ok = weekday in ctx.household.nonveg_days
    fasting = [m for m in ctx.household.members if weekday in m.fasting_days]
    base = [m for m in ctx.household.members if m not in fasting] or ctx.household.members
    if rid is None:  # auto-pick a different valid dish (never vrat as base)
        pool = [r for r in ctx.recipes if meal_slot in r.meal_types and r.id != pm.recipe_id
                and "fasting" not in r.tags]
        scored = []
        for r in pool:
            st = _status(r, base, weekday, nonveg_ok)
            sep = sum(1 for m in base if st[m.name] and
                      propose_adaptation(r, m, st[m.name]) is None)
            if sep:
                continue
            scored.append((r.id, r))
        scored.sort(key=lambda t: t[0])
        if not scored:
            return {"ok": False, "error": "koi valid alternative nahi mila"}
        rid = scored[0][0]
    r = ctx.by_id[rid]
    if meal_slot not in r.meal_types:
        return {"ok": False, "error": f"{r.name} {meal_slot} me nahi banta"}
    st = _status(r, base, weekday, nonveg_ok)
    adapts: list[Adaptation] = []
    for m in base:
        if not st[m.name]:
            continue
        ad = propose_adaptation(r, m, st[m.name])
        if ad is None:
            alt = _best_for([r for r in ctx.recipes if "fasting" not in r.tags],
                            [m], weekday, nonveg_ok, meal_slot,
                            [], False, ctx.household.cook.skill, __import__("random").Random(0))
            adapts.append(Adaptation(member=m.name,
                                     change=f"separate dish: {alt.name if alt else 'NONE'}",
                                     note=f"dish_id:{alt.id}" if alt else "CONFLICT"))
        else:
            adapts.append(ad)
    old = pm.dish
    pm.recipe_id, pm.dish, pm.adaptations = r.id, r.name, adapts
    for rs in ctx.plan.reasons:
        if rs.day_index == days[0].day_index and rs.slot == meal_slot:
            rs.dish = r.name
            rs.why.append(f"user swap: {old} -> {r.name}")
            rs.adapted_for = [a.member for a in adapts]
    ctx.persist()
    return {"ok": True, "day": weekday, "slot": meal_slot, "old": old, "new": r.name,
            "adaptations": [a.model_dump() for a in adapts]}


def t_swap_meal(ctx: Any, a: SwapMealArgs) -> dict:
    return _swap_target(ctx, a.day, a.slot, a.new_dish)


def t_explain_meal(ctx: Any, a: ExplainMealArgs) -> dict:
    if ctx.plan is None:
        return {"ok": False, "error": "no plan yet"}
    weekday = norm_day(a.day)
    meal_slot = norm_slot(a.slot)
    for d in ctx.plan.days:
        if d.weekday == weekday:
            for m in d.meals:
                if m.slot == meal_slot:
                    rs = next((x for x in ctx.plan.reasons
                               if x.day_index == d.day_index and x.slot == meal_slot), None)
                    return {"ok": True, "dish": m.dish,
                            "why": rs.why if rs else [],
                            "adaptations": [x.model_dump() for x in m.adaptations]}
    return {"ok": False, "error": "meal not found"}


def t_build_grocery_list(ctx: Any, a: BuildGroceryListArgs) -> dict:
    if ctx.plan is None:
        return {"ok": False, "error": "pehle plan banao"}
    ctx.snapshot_cart()
    from app.engine.groceries import to_base as _to_base
    needs = aggregate_needs(ctx.plan, ctx.by_id)
    consumed = 0
    for s in ctx.shortfalls:  # kitchen shortfalls feed the next run (consumed once)
        try:
            q, kind = _to_base(float(s["qty"]), str(s["unit"]), str(s["item"]))
        except (ValueError, KeyError, TypeError):
            continue
        if s["item"] in needs:
            needs[s["item"]] = (round(needs[s["item"]][0] + q, 2), needs[s["item"]][1])
        else:
            needs[s["item"]] = (round(q, 2), kind)
        consumed += 1
    ctx.shortfalls = []
    net = subtract_pantry(needs, ctx.household.pantry)
    lines, uncovered = round_to_packs(net, ctx.catalog)
    lines, missing = apply_stockouts(lines, ctx.catalog, seed=a.seed,
                                     allergies=household_allergens(ctx.household))
    ctx.cart, ctx.missing, ctx.uncovered = lines, missing, uncovered
    ctx.total = cart_total(lines)
    ctx.confirmed = False
    ctx.stage = "CONFIRM"
    short_note = f" (+{consumed} kitchen shortfalls)" if consumed else ""
    subs = [f"{ln['item']}<-{ln['substituted']['from']}" for ln in lines if ln.get("substituted")]
    return {"ok": True, "lines": len(lines), "total": ctx.total,
            "budget": ctx.household.budget_inr, "missing": missing,
            "uncovered": uncovered, "substitutions": subs,
            "shortfalls_consumed": consumed, "note": short_note.strip()}


def t_edit_cart(ctx: Any, a: EditCartArgs) -> dict:
    if not ctx.cart:
        return {"ok": False, "error": "cart khaali hai"}
    ctx.snapshot_cart()
    ctx.cart = edit_cart(ctx.cart, a.sku, a.packs)
    ctx.total = cart_total(ctx.cart)
    ctx.confirmed = False  # cart changed -> re-confirm
    return {"ok": True, "lines": len(ctx.cart), "total": ctx.total}


def t_undo(ctx: Any, _a: UndoArgs) -> dict:
    if not ctx.cart_history:
        return {"ok": False, "error": "undo ke liye kuch nahi"}
    ctx.cart, ctx.missing, ctx.total = ctx.cart_history.pop()
    ctx.confirmed = False
    return {"ok": True, "lines": len(ctx.cart), "total": ctx.total}


def t_place_order(ctx: Any, a: PlaceOrderArgs) -> dict:
    if not ctx.cart:
        return {"ok": False, "error": "cart khaali hai — pehle grocery list banao"}
    if not (a.confirm and ctx.confirmed):
        return {"ok": False, "error": "confirm pending — pehle 'haan, order karo' bolo",
                "need_confirm": True}
    order = place_order(ctx.cart, seed=CONFIG.grocery_seed)
    order["missing_noted"] = ctx.missing
    ctx.persist_run(order["order_id"])
    ctx.stage = "HANDOFF"
    return {"ok": True, **order}


def t_send_whatsapp(ctx: Any, _a: Any = None) -> dict:
    if not ctx.cart:
        return {"ok": False, "error": "cart khaali hai — pehle grocery list banao"}
    msg = render_whatsapp("Ghar", ctx.days_to_plan, ctx.cart, ctx.total,
                          ctx.household.budget_inr, ctx.missing, ctx.uncovered)
    ctx.persist_run(None)
    ctx.stage = "HANDOFF"
    return {"ok": True, "simulated": True, "message": msg}


def t_get_pantry(ctx: Any, _a: Any = None) -> dict:
    return {"ok": True, "pantry": ctx.household.pantry}


def t_update_pantry(ctx: Any, a: UpdatePantryArgs) -> dict:
    ctx.household.pantry[a.item] = {"qty": a.qty, "unit": a.unit}
    return {"ok": True, "item": a.item, "pantry_size": len(ctx.household.pantry)}


def t_get_daily_brief(ctx: Any, a: DailyBriefArgs) -> dict:
    from app.engine import kitchen as K
    from app.engine.planner import WEEK as _W
    if ctx.plan is None:
        return {"ok": False, "error": "plan nahi hai"}
    wd = a.weekday or _W[ctx.cook_day_index % len(_W)]
    try:
        wd = norm_day(wd)
    except ValueError:
        return {"ok": False, "error": f"unknown day: {a.weekday}"}
    return K.daily_brief(ctx.plan, ctx.household, wd, ctx.by_id)


def t_report_disruption(ctx: Any, a: ReportDisruptionArgs) -> dict:
    from app.engine import kitchen as K
    from app.engine.planner import WEEK as _W
    if ctx.plan is None:
        return {"ok": False, "error": "plan nahi hai"}
    wd = norm_day(a.day) if a.day else _W[ctx.cook_day_index % len(_W)]
    slot = norm_slot(a.slot) if a.slot else "dinner"
    if a.kind == "missing_ingredient":
        r = K.handle_missing_ingredient(ctx.plan, ctx.household, wd, a.detail,
                                        ctx.recipes, ctx.by_id)
    elif a.kind == "extra_guests":
        m = re.search(r"(\d+)", a.detail)
        r = K.handle_extra_guests(ctx.plan, wd, int(m.group(1)) if m else 2,
                                  slot, ctx.by_id)
    elif a.kind == "equipment_broken":
        r = K.handle_equipment_broken(ctx.plan, ctx.household, wd, a.detail or "cooker",
                                      ctx.recipes, ctx.by_id)
    else:  # cook_leave / low_energy -> simplify
        r = K.handle_cook_leave(ctx.plan, ctx.household, wd, ctx.recipes, ctx.by_id)
    if r.get("ok") and r.get("shortfall"):
        ctx.shortfalls.extend(r["shortfall"])
    if r.get("ok"):
        ctx.persist()
    return {"ok": r.get("ok", False), **{k: v for k, v in r.items() if k != "ok"}}


def t_log_cooked(ctx: Any, a: LogCookedArgs) -> dict:
    from app.engine import kitchen as K
    from app.engine.planner import WEEK as _W
    if ctx.plan is None:
        return {"ok": False, "error": "plan nahi hai"}
    wd = _W[ctx.cook_day_index % len(_W)]
    slot = norm_slot(a.slot)
    day = next((d for d in ctx.plan.days if d.weekday == wd), None)
    dish = next((m.dish for m in day.meals if m.slot == slot), "") if day else ""
    ctx.log_cook(wd, slot, dish, a.status, a.note)
    out: dict = {"ok": True, "day": wd, "slot": slot, "dish": dish, "status": a.status}
    tnote = K.note_from_feedback(dish, a.note)
    if tnote:
        ctx.taste_notes.append(tnote)
        out["taste_note"] = tnote
    if slot == "dinner" and a.status == "cooked" and ctx.cook_day_index + 1 < len(ctx.plan.days):
        ctx.cook_day_index += 1
        out["next_day"] = _W[ctx.cook_day_index % len(_W)]
    return out


TOOLS: dict[str, tuple[Any, Callable]] = {
    "add_member": (AddMemberArgs, t_add_member),
    "update_household": (UpdateHouseholdArgs, t_update_household),
    "set_constraint": (SetConstraintArgs, t_set_constraint),
    "generate_plan": (GeneratePlanArgs, t_generate_plan),
    "swap_meal": (SwapMealArgs, t_swap_meal),
    "explain_meal": (ExplainMealArgs, t_explain_meal),
    "build_grocery_list": (BuildGroceryListArgs, t_build_grocery_list),
    "edit_cart": (EditCartArgs, t_edit_cart),
    "undo": (UndoArgs, t_undo),
    "place_order": (PlaceOrderArgs, t_place_order),
    "send_whatsapp": (NoArgs, t_send_whatsapp),
    "get_pantry": (NoArgs, t_get_pantry),
    "update_pantry": (UpdatePantryArgs, t_update_pantry),
    "get_daily_brief": (DailyBriefArgs, t_get_daily_brief),
    "report_disruption": (ReportDisruptionArgs, t_report_disruption),
    "log_cooked": (LogCookedArgs, t_log_cooked),
}


def dispatch(ctx: Any, name: str, args: dict) -> dict:
    """Validate (strict) -> run. One normalize-and-retry on ValidationError."""
    if name not in TOOLS:
        return {"ok": False, "error": f"unknown tool: {name}"}
    schema, fn = TOOLS[name]
    try:
        parsed = schema.model_validate(args)
    except ValidationError as e:
        fixed = dict(args)
        for k, v in list(fixed.items()):
            if isinstance(v, str):
                fixed[k] = v.strip()
        if "day" in fixed:
            try:
                fixed["day"] = norm_day(str(fixed["day"]))
            except ValueError:
                pass
        if "slot" in fixed:
            try:
                fixed["slot"] = norm_slot(str(fixed["slot"]))
            except ValueError:
                pass
        try:
            parsed = schema.model_validate(fixed)
        except ValidationError:
            return {"ok": False, "error": f"bad args for {name}: {e.errors()[0]['msg']}"}
    try:
        return fn(ctx, parsed)
    except Exception as e:
        return {"ok": False, "error": f"{name} failed: {e}"}
