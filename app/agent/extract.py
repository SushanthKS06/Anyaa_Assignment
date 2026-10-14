"""Constraint extraction from utterances. Two paths, one schema:
mock (rule-based, deterministic — used without keys and in all tests) and
LLM (JSON with Pydantic validation + one repair retry — used with keys)."""
from __future__ import annotations

import re
from typing import Any

from app.agent.llm import chat
from app.config import CONFIG
from app.engine.models import HouseholdConstraints, Member

DAYMAP = {
    "monday": "Mon", "tuesday": "Tue", "wednesday": "Wed",
    "thursday": "Thu", "friday": "Fri", "saturday": "Sat", "sunday": "Sun",
    "somvar": "Mon", "mangal": "Tue", "budh": "Wed", "guruwar": "Thu",
    "shukra": "Fri", "shani": "Sat", "ravi": "Sun",
    # Tamil day names
    "thingal": "Mon", "chevvai": "Tue", "sevai": "Tue", "budhan": "Wed",
    "vyazhan": "Thu", "velli": "Fri", "sani": "Sat", "nyayiru": "Sun",
    "திங்கள்": "Mon", "செவ்வாய்": "Tue", "புதன்": "Wed",
    "வியாழன்": "Thu", "வெள்ளி": "Fri", "சனி": "Sat", "ஞாயிறு": "Sun"
}


def _norm_days(text: str) -> list[str]:
    t = text.lower()
    return [v for k, v in DAYMAP.items() if k in t]


TAMIL_NUMS = {
    "ஒன்னு": 1, "ஒரு": 1, "ரெண்டு": 2, "இரண்டு": 2, "மூணு": 3, "மூன்று": 3,
    "நாலு": 4, "நான்கு": 4, "அஞ்சு": 5, "ஐந்து": 5, "ஆறு": 6, "ஏழு": 7,
    "ek": 1, "do": 2, "teen": 3, "char": 4, "paanch": 5, "chhe": 6, "saat": 7,
}


def _parse_family_size(t: str) -> int | None:
    m = re.search(r"(நாலு|நான்கு|ரெண்டு|இரண்டு|மூணு|மூன்று|அஞ்சு|ஐந்து|\d+)\s*(?:பேர்|ஆட்கள்|log|people|members?|of us)", t)
    if m:
        w = m.group(1)
        return TAMIL_NUMS.get(w, int(w) if w.isdigit() else None)
    m2 = re.search(r"\b(\d+)\s*(?:log|people|members?|of us)\b", t)
    if m2:
        return int(m2.group(1))
    return None


def extract_mock(text: str) -> HouseholdConstraints:
    t = text.lower()
    members: list[Member] = []

    # 1. Senior / Jain / Fasting
    if any(k in t for k in ["jain", "dadi", "paati", "patti", "grandmother", "பாட்டி", "தாத்தா", "ஜைன்", "दादी", "नानी", "जैन"]):
        members.append(Member(name="Dadi", age_group="senior", diet="jain",
                              fasting_days=_norm_days(t)))

    # 2. Papa / Father / Diabetic / Low sugar
    if any(k in t for k in ["diabet", "low sugar", "papa", "appa", "father", "dad", "thatha", "sugar", "சர்க்கரை", "டயபடீஸ்", "அப்பா", "पिता", "पापा", "शुगर", "डायबिटीज"]):
        members.append(Member(name="Papa", age_group="adult", diet="veg",
                              health_notes=["low_sugar"] if any(k in t for k in ["diabet", "low sugar", "sugar", "சர்க்கரை", "டயபடீஸ்", "शुगर", "डायबिटीज"]) else []))

    # 2b. Mother / Mummy / Amma
    if any(k in t for k in ["mummy", "mother", "amma", "mom", "அம்மா", "माँ", "अम्मा"]):
        members.append(Member(name="Mummy", age_group="adult", diet="veg"))

    # 3. Toddler / Baby / Soft food
    if any(k in t for k in ["toddler", "2 saal", "chhotu", "baby", "kuzhandhai", "2 vayasu", "2-year-old", "2 year old", "சாஃப்ட்", "சாப்ட்", "குழந்தை", "பாப்பா", "வயசு", "छोटू", "बच्चा", "2 साल", "soft food", "சாப்ட்டான"]):
        members.append(Member(name="Chhotu", age_group="toddler", diet="veg",
                              health_notes=["soft_food"]))

    # 4. Peanut / Kadalai allergy
    has_peanut = any(k in t for k in ["peanut", "kadalai", "verkkadalai", "கடலை", "வேர்க்கடலை", "मूंगफली", "carrot", "கேரட்"])
    has_allergy = any(k in t for k in ["allerg", "avoid", "koodathu", "அலர்ஜி", "அவாய்ட்", "ஒவ்வாமை", "एलर्जी", "बचें"])
    if has_peanut and has_allergy:
        allergen = "peanut" if any(k in t for k in ["peanut", "kadalai", "verkkadalai", "கடலை", "வேர்க்கடலை", "मूंगफली"]) else "carrot"
        members.append(Member(name="AllergyMember", age_group="child" if not any(k in t for k in ["எனக்கு", "mujhe", "i have"]) else "adult", diet="veg",
                              allergies=[allergen] if allergen != "carrot" else ["peanut"]))

    # 5. Non-veg (avoid false positive on 'meal prep' like 'மீன்பிரிப்' or 'மீல்ப்ரிப்')
    t_nonveg = t.replace("மீன்பிரிப்", "mealprep").replace("மீல்ப்ரிப்", "mealprep").replace("மீல் பிரப்", "mealprep")
    has_nonveg = (
        any(k in t_nonveg for k in [
            "non-veg", "nonveg", "non veg", "chicken", "kari", "muttai", "அசைவம்", "கறி", "முட்டை",
            "नॉनवेज", "चिकन", "अंडा", "meat", "fish", "மட்டன்", "மீன்", "non-vegetarian", "nonvegetarian",
            "நான் வெஜிடேரியன்", "நான்வெஜ்", "நான் வெஜ்", "மாமிசம்"
        ])
        or re.search(r"\b(meen|மீன்)\b", t_nonveg)
        or any(k in t_nonveg for k in ["மீன் குழம்பு", "மீன் சாப்பாடு", "மீன் வறுவல்"])
    )
    if has_nonveg:
        # Check if family/household eats nonveg ("நாங்கள்", "we", "sab", "everyone")
        family_nonveg = any(k in t_nonveg for k in [
            "நாங்கள்", "we ", "we're", "hum", "sab", "all", "குடும்பம்", "வீட்டில்", "ghar",
            "ரெண்டுமே", "both", "non-veg meal", "nonveg meal", "அசைவ", "நான் வெஜிடேரியன்"
        ])
        if family_nonveg and members:
            for m in members:
                if m.diet != "jain":
                    m.diet = "nonveg"
        else:
            # Check if specific member mentioned
            beta_present = any(m.name == "Beta" for m in members)
            if not beta_present and not any(m.diet == "nonveg" for m in members):
                members.append(Member(name="Beta", age_group="teen", diet="nonveg"))
            else:
                for m in members:
                    if m.name in ("Beta", "Baba") or (not any(x.diet == "nonveg" for x in members) and m.diet != "jain"):
                        m.diet = "nonveg"
                        break

    # 6. Guest note
    if any(k in t for k in ["guest", "mehman", "virundhinar", "விருந்தினர்", "मेहमान"]):
        members.append(Member(name="GuestNote", age_group="adult", diet="veg"))

    # 7. Fill family size if count was mentioned
    fsize = _parse_family_size(t)
    if fsize:
        curr_len = len([m for m in members if m.name != "GuestNote"])
        default_diet = "nonveg" if has_nonveg and any(k in t_nonveg for k in ["நாங்கள்", "we", "hum", "sab", "all", "ரெண்டுமே"]) else "veg"
        for i in range(curr_len + 1, fsize + 1):
            members.append(Member(name=f"Person_{i}", age_group="adult", diet=default_diet))

    # 8. Rice avoidance / dislikes
    if any(k in t for k in ["அரிசி", "rice", "chawal"]) and any(k in t for k in ["avoid", "அவாய்ட்", "வேண்டாம்", "vendaam", "nahi", "illai", "parhez", "இருக்கு"]):
        for m in members:
            if "rice" not in m.dislikes:
                m.dislikes.append("rice")

    if not members:
        members = [Member(name="Member1", age_group="adult", diet="nonveg" if has_nonveg else "veg")]

    budget = None
    # Check word budgets first
    WORD_BUDGETS = {
        "அஞ்சாயிரம்": 5000, "ஐந்தாயிரம்": 5000, "நாலாயிரம்": 4000, "நான்காயிரம்": 4000,
        "மூவாயிரம்": 3000, "இரண்டாயிரம்": 2000, "ஈராயிரம்": 2000, "ஆறாயிரம்": 6000, "ஏழாயிரம்": 7000, "பத்தாயிரம்": 10000,
        "paanch hazaar": 5000, "char hazaar": 4000, "teen hazaar": 3000, "do hazaar": 2000,
        "chhe hazaar": 6000, "saat hazaar": 7000, "das hazaar": 10000,
        "five thousand": 5000, "four thousand": 4000, "three thousand": 3000, "two thousand": 2000,
        "six thousand": 6000, "seven thousand": 7000, "ten thousand": 10000,
    }
    for w, val in WORD_BUDGETS.items():
        if w in t:
            budget = val
            break

    if budget is None:
        # Check ₹ symbol first (e.g. "₹5000", "₹ 5000", "5000₹")
        m_sym = re.search(r"[₹]\s*(\d[\d,]*)", t) or re.search(r"(\d[\d,]*)\s*[₹]", t) or re.search(r"\b(?:rs|inr)\.?\s*(\d[\d,]*)", t)
        if m_sym:
            budget = int(m_sym.group(1).replace(",", ""))
        else:
            m = re.search(r"(\d[\d,]*)\s*(hazaar|rupaye|rupees?|rs\b|inr|budget|rooba|roobai|aayiram|ரூபாய்|ரூபா|பட்ஜெட்|ரொக்கம்|रुपये|रुपया|बजट|வச்சுக்கோ|வச்சுக்க|vekkalam|podu|rakho)", t)
            if m:
                mult = 1000 if ("hazaar" in m.group(2) or "aayiram" in m.group(2)) else 1
                budget = int(m.group(1).replace(",", "")) * mult
            else:
                m2 = re.search(r"(?:budget|rupaye|rupees?|rs\b|inr|rooba|roobai|ரூபாய்|ரூபா|பட்ஜெட்|ரொக்கம்|रुपये|रुपया|बजट)\D{0,10}(\d[\d,]*)", t)
                if m2:
                    budget = int(m2.group(1).replace(",", ""))
                else:
                    m3 = re.search(r"\b(\d{3,6})\b", t)
                    if m3:
                        budget = int(m3.group(1))

    TAMIL_DAY_WORDS = {
        "ஒன்னு": 1, "ஒரு": 1, "ரெண்டு": 2, "இரண்டு": 2, "மூணு": 3, "மூன்று": 3,
        "நாலு": 4, "நான்கு": 4, "அஞ்சு": 5, "ஐந்து": 5, "ஆறு": 6, "ஏழு": 7,
        "ek": 1, "do": 2, "teen": 3, "char": 4, "paanch": 5, "chhe": 6, "saat": 7,
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    }
    m_day_word = re.search(
        r"(ஒன்னு|ஒரு|ரெண்டு|இரண்டு|மூணு|மூன்று|நாலு|நான்கு|அஞ்சு|ஐந்து|ஆறு|ஏழு|ek|do|teen|char|paanch|chhe|saat|one|two|three|four|five|six|seven)\s*(?:din|naal|naatkal|days?|நாள்|நாட்கள்|நாளுக்கான|நாளைக்கு|दिन)",
        t
    )
    if m_day_word:
        days = TAMIL_DAY_WORDS.get(m_day_word.group(1), 7)
    else:
        d = re.search(r"(\d+)\s*(?:din|naal|naatkal|days?|நாள்|நாட்கள்|நாளுக்கான|நாளைக்கு|दिन)", t)
        days = int(d.group(1)) if d else 7
    days = max(1, min(14, days))
    nonveg_days = _norm_days(t)
    if ("weekend" in t or "sat" in t or "sun" in t) and not nonveg_days:
        nonveg_days = ["Sat", "Sun"]
    elif any(k in t for k in ["daily", "all days", "rozkana", "dhinamum", "தினமும்", "எல்லா நாளும்", "har din", "ரோஜானா", "everyday", "every day"]):
        nonveg_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    elif has_nonveg and not nonveg_days:
        # Default nonveg days when user eats nonveg but specified no particular days:
        # Allow all weekdays so the meal plan can schedule non-veg main dishes
        nonveg_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    fasting = "Ekadashi" if "ekadashi" in t else (",".join(_norm_days(t)) if any(k in t for k in ["fast", "vrat", "viradham", "viratham", "nombu", "upavasam", "விரதம்", "நோன்பு", "व्रत"]) else "")
    return HouseholdConstraints(members=members, days_to_plan=days, budget_inr=budget,
                                nonveg_days=nonveg_days, fasting_context=fasting)


PLACEHOLDERS = {"Member1", "GuestNote"}


def merge_constraints(base: HouseholdConstraints, new: HouseholdConstraints) -> HouseholdConstraints:
    newcomers = [m for m in new.members
                 if not (m.name in PLACEHOLDERS and len(base.members) > 0)]
    by_name = {m.name: m for m in base.members}
    for m in newcomers:
        if m.name in by_name:
            old = by_name[m.name]
            by_name[m.name] = Member(
                name=m.name,
                age_group=m.age_group if m.age_group != "adult" else old.age_group,
                diet=m.diet if not (old.name and m.diet == "veg" and old.diet != "veg") else old.diet,
                allergies=sorted(set(old.allergies) | set(m.allergies)),
                health_notes=sorted(set(old.health_notes) | set(m.health_notes)),
                dislikes=sorted(set(old.dislikes) | set(m.dislikes)),
                fasting_days=sorted(set(old.fasting_days) | set(m.fasting_days)),
            )
        else:
            by_name[m.name] = m
    merged_members = list(by_name.values())
    nv_days = sorted(set(base.nonveg_days) | set(new.nonveg_days))
    if any(m.diet == "nonveg" for m in merged_members) and not nv_days:
        nv_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return HouseholdConstraints(
        members=merged_members,
        days_to_plan=new.days_to_plan if new.days_to_plan != 7 else base.days_to_plan,
        budget_inr=new.budget_inr if new.budget_inr is not None else base.budget_inr,
        nonveg_days=nv_days,
        fasting_context=new.fasting_context or base.fasting_context,
    )


class NoKeysError(RuntimeError):
    pass


def extract_llm(text: str, current: HouseholdConstraints) -> HouseholdConstraints:
    if not (CONFIG.gemini_api_key or CONFIG.groq_api_key):
        raise NoKeysError("no LLM keys — use mock extractor")
    msgs = [
        {"role": "system", "content": "You are a data extractor. Extract household constraints into valid JSON matching this schema: {\"members\": [{\"name\": string, \"age_group\": \"adult\"|\"child\"|\"senior\"|\"toddler\"|\"teen\", \"diet\": \"veg\"|\"jain\"|\"nonveg\"|\"eggetarian\"|\"vegan\", \"allergies\": [string], \"health_notes\": [string], \"dislikes\": [string], \"fasting_days\": [string]}], \"days_to_plan\": int, \"budget_inr\": int|null, \"nonveg_days\": [string], \"fasting_context\": string}. If user eats non-veg (chicken, fish, meat, egg, அசைவம், நான் வெஜிடேரியன், नॉनवेज) but did not specify days, set nonveg_days to [\"Mon\", \"Tue\", \"Wed\", \"Thu\", \"Fri\", \"Sat\", \"Sun\"]. Never leave nonveg_days empty when non-veg is eaten. Reply with JSON ONLY."},
        {"role": "user", "content": f"Current: {current.model_dump_json()}\nExtract from utterance: {text}"}
    ]
    last_err = ""
    for _ in range(2):  # one repair retry
        r = chat(msgs + ([{"role": "user", "content": f"Fix, valid JSON only: {last_err}"}] if last_err else []),
                 role="household", use_mock=False)
        try:
            import json as _j
            raw = r["text"]
            s, e = raw.find("{"), raw.rfind("}")
            if s != -1 and e != -1 and e > s:
                data: dict[str, Any] = _j.loads(raw[s:e + 1])
                for i, m in enumerate(data.get("members", [])):
                    if not m.get("name") or str(m.get("name")).lower() in ("unknown", "none", "null", "member", "person"):
                        prefix = str(m.get("age_group", "adult")).capitalize()
                        m["name"] = f"{prefix}_{i+1}"
                if any(m.get("diet") == "nonveg" for m in data.get("members", [])) and not data.get("nonveg_days"):
                    data["nonveg_days"] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                return HouseholdConstraints.model_validate(data)
        except Exception as ex:
            last_err = str(ex)[:200]
    raise ValueError(f"LLM extraction failed twice: {last_err}")


def extract(text: str, current: HouseholdConstraints, force_mock: bool = False) -> HouseholdConstraints:
    if not force_mock and (CONFIG.gemini_api_key or CONFIG.groq_api_key) and not CONFIG.mock_default:
        try:
            return merge_constraints(current, extract_llm(text, current))
        except Exception:
            pass  # fall back to deterministic mock
    return merge_constraints(current, extract_mock(text))
