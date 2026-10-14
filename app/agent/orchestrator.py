"""Orchestrator: text-first state machine. COLLECT -> PLAN -> NEGOTIATE ->
GROCERIES -> CONFIRM -> CHECKOUT -> HANDOFF. The orchestrator owns CONTENT
(deterministic templates + tool results); the LLM only polishes tone when keys
exist. CODE DECIDES: confirm-gating, swaps, cart math all live here/in tools."""
from __future__ import annotations

import json
import re
import time

from app.agent import tools as T
from app.agent.extract import extract, merge_constraints
from app.agent.llm import chat
from app.agent.personas import AGENT_NAME, COOK_SYSTEM, HOUSEHOLD_SYSTEM, localize_reply
from app.agent.router import detect_language, detect_mode
from app.config import CONFIG
from app.engine.instamart_mock import load_catalog
from app.engine.models import Household, HouseholdConstraints
from app.engine.planner import WEEK, load_recipes
from app.engine.recipe_steps import format_recipe_instructions
from app.store.db import get_conn

STAGES = ("COLLECT", "PLAN", "NEGOTIATE", "GROCERIES", "CONFIRM", "CHECKOUT", "HANDOFF")

CORRECT_RE = re.compile(r"nahi wait|galat|sorry|correction|maine kaha|actually|mistake|illai|thappu|maathu|இல்லை|தவறு|மாற்று|गलत|नहीं रुको|माफ|बदलो")
CONFIRM_RE = re.compile(r"\bhaan\b|confirm|pakka|theek hai|bilkul|kar do|yes|aam|seri|kandippa|pannunga|podunga|சரி|ஆம்|கண்டிப்பா|பண்ணுங்க|போடுங்க|உறுதி|हाँ|पक्का|ठीक है|बिल्कुल|कर दो|हां")
ORDER_RE = re.compile(r"order|instamart|kharid|mangwa|vaangu|ஆர்டர்|வாங்கு|வாங்க|கொள்முதல்|ऑर्डर|खरीद|मंगवाओ|मंगाओ")
SWAP_RE = re.compile(r"swap|badal|change|nahi.*bana|ban[ao].*do|ki jagah|maathu|badhil|மாற்று|மாத்து|பதில்|பதிலாக|வேண்டாம்|बदलो|बदल|की जगह|मत बनाओ")
EXPLAIN_RE = re.compile(r"kyun|kyon|why|kaise|explain|kaun sa.*kyun|yean|yen|eppadi|ஏன்|எதற்கு|எப்படி|விளக்கு|சொல்|क्यों|कैसे|बताओ|कारण")
GROCERY_RE = re.compile(r"grocery|saaman|samaan|list bana|cart|khareed|maligai|porul|மளிகை|பொருட்கள்|பட்டியல்|கார்ட்|सामान|किराना|लिस्ट|सब्जी")
WA_RE = re.compile(r"whatsapp|message|bhej|send|anuppu|வாட்ஸ்அப்|அனுப்பு|செய்தி|व्हाट्सएप|भेज|मैसेज")
UNDO_RE = re.compile(r"undo|wapas|thirumba|திரும்பு|திரும்ப|வேண்டாம்|वापस|अनडू|ரद्द")
MORE_RE = re.compile(r"\baur\b|next|aage|continue|batao|aduthu|innum|sollunga|அடுத்து|இன்னும்|சொல்லுங்க|தொடரவும்|மேலும்|और|आगे|और बताओ|सुनाओ")
PLAN_RE = re.compile(r"plan bana|plan kar|shuru|start|plan pannu|aarambi|பிளான்|plan.*கொடு|plan.*குடு|plan.*போடு|பிளானை|meal.*prep|மீன்பிரிப்|மீல்ப்ரிப்|திட்டம்|உணவு திட்டம்|प्लान|शुरू")
NONVEG_PLAN_RE = re.compile(
    r"(?:plan|meal|menu|khana|samayal|saapaadu|sapadu|சாப்பாடு|உணவு|திட்டம்|பிளான்|खाना|प्लान|மீல்).*(?:non[-\s]?veg|chicken|fish|meat|egg|அசைவ|நான்வெஜ்|நॉनवेज|मांसाहारी)|"
    r"(?:non[-\s]?veg|chicken|fish|meat|egg|அசைவ|நான்வெஜ்|நॉनवेज|मांसाहारी).*(?:plan|meal|menu|make|change|should be|all|full|complete|done|போடு|பண்ணு|வேணும்|செய்|மாற்று|बनाओ|चाहिए|होना|बदलो)",
    re.IGNORECASE
)
PANTRY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(kilo|kg|gram|g\b|litre|l\b|ml|pack|pieces?)\s*([a-z_]+)\s*(?:hai|irukku)")
QTYMAP = {"kilo": ("kg", 1), "kg": ("kg", 1), "gram": ("g", 1), "g": ("g", 1),
          "litre": ("l", 1), "l": ("l", 1), "ml": ("ml", 1)}


class OrchestratorState:
    def __init__(self, hid: str | None = None) -> None:
        self.hid = hid or f"hh-{int(time.time())}"
        self.mode = "household"
        self.stage = "COLLECT"
        self.household = Household(members=[])
        self.constraints = HouseholdConstraints()
        self.days_to_plan = 7
        self.recipes = load_recipes()
        self.by_id = {r.id: r for r in self.recipes}
        self.catalog = load_catalog()
        self.plan = None
        self.cart: list[dict] = []
        self.missing: list[str] = []
        self.uncovered: list[str] = []
        self.total = 0.0
        self.confirmed = False
        self.pending_confirm = False
        self.cart_history: list[tuple] = []
        self.presented_until = 0
        self.last_meal: tuple[str, str] | None = None  # (weekday, slot)
        self.cook_day_index = 0
        self.shortfalls: list[dict] = []
        self.taste_notes: list[str] = []
        self.transcript: list[dict] = []
        self.lang = "hi-IN"
        get_conn(CONFIG.db_path).close()

    def cook_weekday(self) -> str:
        return WEEK[self.cook_day_index % len(WEEK)]

    def log_cook(self, weekday: str, slot: str, dish: str, status: str, note: str) -> None:
        conn = get_conn(CONFIG.db_path)
        conn.execute("INSERT INTO cook_logs VALUES(?,?,?,?)",
                     (self.hid, weekday,
                      json.dumps({"slot": slot, "dish": dish, "status": status, "note": note}),
                      time.time()))
        conn.commit()
        conn.close()

    # -- helpers --
    def snapshot_cart(self) -> None:
        self.cart_history.append((list(self.cart), list(self.missing), self.total))

    def say(self, role: str, text: str, calls: list[dict] | None = None) -> str:
        self.transcript.append({"role": role, "text": text, "tools": calls or []})
        return self._polish(text) if role == "assistant" else text

    def _polish(self, text: str) -> str:
        lang = getattr(self, "lang", "hi-IN")
        # Preserve pristine structured recipe instructions with exact quantities & steps
        if "📦" in text and ("👨‍🍳" in text or "Step-by-Step" in text or "செய்முறை" in text or "पकाने की विधि" in text or "Items Used" in text):
            return text
        if CONFIG.mock_default or not (CONFIG.gemini_api_key or CONFIG.groq_api_key):
            return localize_reply(text, lang)
        try:
            sys = HOUSEHOLD_SYSTEM if self.mode == "household" else COOK_SYSTEM
            if "\n• " in text or "செய்முறை" in text or "Cooking Steps" in text or "portions)" in text or "Items Used" in text:
                if lang == "ta-IN":
                    lang_prompt = "You MUST speak ONLY in Tamil script. Translate and express the following recipe details and quantities warmly, completely, and accurately in Tamil without dropping or skipping any numbers, items, or quantities. Do NOT use any Hindi words:\n"
                elif lang == "en-IN":
                    lang_prompt = "You MUST speak ONLY in natural English. Present the following recipe details and quantities clearly, completely, and accurately in English without dropping or skipping any numbers, items, or quantities. Do NOT use any Hindi words:\n"
                else:
                    lang_prompt = "Express the following recipe details and quantities clearly, completely, and warmly in Hindi / Hinglish without dropping or skipping any numbers, items, or quantities:\n"
            else:
                if lang == "ta-IN":
                    lang_prompt = "You MUST speak ONLY in Tamil script. Express the following message naturally, warmly, and completely in Tamil without omitting or skipping any dishes, items, or details. Never use any Hindi words:\n"
                elif lang == "en-IN":
                    lang_prompt = "You MUST speak ONLY in natural English. Express the following message clearly, warmly, and completely in English without omitting or skipping any dishes, items, or details. Never use any Hindi words:\n"
                else:
                    lang_prompt = "Express the following message naturally, warmly, and completely in Hindi / Hinglish without omitting or skipping any dishes, items, or details:\n"

            r = chat([{"role": "system", "content": sys},
                      {"role": "user", "content": f"{lang_prompt}{text}"}],
                     role=self.mode, use_mock=False)
            res = (r.get("text") or "").strip()
            return res or localize_reply(text, lang)
        except Exception:
            return localize_reply(text, lang)

    def call(self, name: str, args: dict) -> dict:
        res = T.dispatch(self, name, args)
        self.transcript.append({"role": "tool", "text": f"{name}({args})",
                                "tools": [{"result": res}]})
        return res

    def persist(self) -> None:
        conn = get_conn(CONFIG.db_path)
        conn.execute("INSERT OR REPLACE INTO households(id,name,budget_inr,created_ts) VALUES(?,?,?,?)",
                     (self.hid, "Ghar", self.household.budget_inr, time.time()))
        conn.execute("DELETE FROM members WHERE household_id=?", (self.hid,))
        for m in self.household.members:
            conn.execute("INSERT INTO members VALUES(?,?,?,?,?,?,?,?)",
                          (self.hid, m.name, m.age_group, m.diet,
                           json.dumps(m.allergies), json.dumps(m.health_notes),
                           json.dumps(m.dislikes), json.dumps(m.fasting_days)))
        if self.plan is not None:
            conn.execute("DELETE FROM plans WHERE household_id=?", (self.hid,))
            conn.execute("INSERT INTO plans VALUES(?,?,?,?)",
                         (self.hid, self.plan.model_dump_json(),
                          json.dumps([r.model_dump() for r in self.plan.reasons]), time.time()))
        conn.commit()
        conn.close()

    def persist_run(self, order_id: str | None) -> None:
        conn = get_conn(CONFIG.db_path)
        conn.execute("INSERT INTO grocery_runs VALUES(?,?,?,?,?)",
                     (self.hid, json.dumps(self.cart), self.total, order_id, time.time()))
        conn.commit()
        conn.close()

    # -- presentation --
    def present_days(self, n: int = 2) -> str:
        assert self.plan is not None
        lines = []
        slot_map_ta = {"breakfast": "காலை", "lunch": "மதியம்", "dinner": "இரவு", "snack": "சிற்றுண்டி", "tiffin": "டிபன்"}
        day_map_ta = {"Mon": "திங்கள் (Mon)", "Tue": "செவ்வாய் (Tue)", "Wed": "புதன் (Wed)", "Thu": "வியாழன் (Thu)", "Fri": "வெள்ளி (Fri)", "Sat": "சனி (Sat)", "Sun": "ஞாயிறு (Sun)"}

        for d in self.plan.days[self.presented_until:self.presented_until + n]:
            parts = []
            for m in d.meals:
                ad_strs = []
                for a in m.adaptations:
                    ch = a.change
                    low = ch.lower()
                    m_nv = re.search(r"(?:nonveg side|separate nonveg dish):\s*([^(\n]+)", ch, re.IGNORECASE)
                    if m_nv:
                        dname_clean = m_nv.group(1).strip()
                        if self.lang == "ta-IN":
                            ad_strs.append(f"+ {a.member}-க்கு {dname_clean}")
                        elif self.lang == "en-IN":
                            ad_strs.append(f"+ {a.member}: {dname_clean}")
                        else:
                            ad_strs.append(f"+ {a.member} ke liye {dname_clean}")
                    elif "fasting" in low or "vrat" in low:
                        m_fast = re.search(r"fasting plate:\s*([^(\n]+)", ch, re.IGNORECASE)
                        fdish = f" ({m_fast.group(1).strip()})" if m_fast else ""
                        if self.lang == "ta-IN":
                            ad_strs.append(f"{a.member}-க்கு விரத உணவு{fdish}")
                        elif self.lang == "en-IN":
                            ad_strs.append(f"{a.member}: fasting plate{fdish}")
                        else:
                            ad_strs.append(f"{a.member} ke liye vrat plate{fdish}")
                    else:
                        m_sep = re.search(r"separate dish:\s*([^(\n]+)", ch, re.IGNORECASE)
                        sdish = f" ({m_sep.group(1).strip()})" if m_sep else ""
                        if self.lang == "ta-IN":
                            ad_strs.append(f"{a.member}-க்கு தனி உணவு{sdish}")
                        elif self.lang == "en-IN":
                            ad_strs.append(f"{a.member}: separate portion{sdish}")
                        else:
                            ad_strs.append(f"{a.member} ke liye alag{sdish}")

                ad_info = f" ({', '.join(ad_strs)})" if ad_strs else ""
                if self.lang == "ta-IN":
                    sname = slot_map_ta.get(m.slot.lower(), m.slot)
                    s = f"{sname}: {m.dish}{ad_info}"
                elif self.lang == "en-IN":
                    s = f"{m.slot.capitalize()}: {m.dish}{ad_info}"
                else:
                    s = f"{m.slot}: {m.dish}{ad_info}"
                parts.append(s)

            dname = day_map_ta.get(d.weekday, d.weekday) if self.lang == "ta-IN" else d.weekday
            lines.append(f"{dname} — " + "; ".join(parts))

        self.presented_until = min(len(self.plan.days), self.presented_until + n)
        if self.lang == "ta-IN":
            more = " அடுத்து கேட்கலாமா? ('அடுத்து' என்று சொல்லுங்கள்)" if self.presented_until < len(self.plan.days) else " அவ்வளவுதான், முழு வாரமும் திட்டமிடப்பட்டது."
        elif self.lang == "en-IN":
            more = " What next? (say 'next' to continue)" if self.presented_until < len(self.plan.days) else " That's all, full week planned."
        else:
            more = " Aur? (aur bolo)" if self.presented_until < len(self.plan.days) else " Bas, poora hafta done."
        return " | ".join(lines) + more

    # -- main --
    def handle_user(self, text: str) -> str:
        t = text.strip()
        if not t:
            if self.lang == "ta-IN":
                return self.say("assistant", "கேட்டுக் கொண்டிருக்கிறேன் — சொல்லுங்கள்?")
            elif self.lang == "en-IN":
                return self.say("assistant", "I am listening — please go ahead.")
            return self.say("assistant", "Sun rahi hu — bolo?")

        # Dynamic tri-lingual mirroring: Tamil -> Tamil, English -> English, Hindi -> Hindi
        self.lang = detect_language(t, current=getattr(self, "lang", "hi-IN"))
        is_first = not self.transcript or not any(e["role"] == "user" for e in self.transcript)
        self.transcript.append({"role": "user", "text": t, "tools": []})
        mode, _sw = detect_mode(t, self.mode)
        self.mode = mode
        low = t.lower()
        is_greeting_only = len(t.split()) <= 4 and any(
            w in low for w in ["வணக்கம்", "vanakkam", "vanakam", "hello", "hi", "hey", "namaste", "namaskar", "pranam"]
        )

        # Mode explicit switches
        if t.strip().lower() == "/cook":
            self.mode = "cook"
            if self.lang == "ta-IN":
                return self.say("assistant", "குக் மோட் (Cook Mode). சொல்லுங்கள் — இன்னைக்கு என்ன சமையல் செய்ய வேண்டும்?")
            elif self.lang == "en-IN":
                return self.say("assistant", "Cook mode active. Tell me — what are we preparing today?")
            return self.say("assistant", "Cook mode. Bolo — aaj kya banana hai?")

        if t.strip().lower() == "/home":
            self.mode = "household"
            if self.lang == "ta-IN":
                return self.say("assistant", "ஹவுஸ்ஹோல்ட் மோட் (Household Mode). சொல்லுங்கள் — உணவு திட்டம், மளிகைப் பட்டியல் அல்லது ஆர்டர் செய்ய வேண்டுமா?")
            elif self.lang == "en-IN":
                return self.say("assistant", "Household mode active. What would you like to do — meal plan, grocery list, or order?")
            return self.say("assistant", "Household mode. Bolo — plan, list ya order?")

        # Greeting handling
        if is_greeting_only and t.strip().lower() not in ("/cook", "/home"):
            if self.mode == "cook":
                if self.lang == "ta-IN":
                    first = f"வணக்கம்! நான் {AGENT_NAME} (Cook Mode). இன்னைக்கு என்ன சமையல் செய்ய வேண்டும்? இன்றைய சமையல் குறிப்பு (brief) வேண்டுமா அல்லது ஏதேனும் உணவின் செய்முறை விளக்கங்கள் தேவையா?"
                elif self.lang == "en-IN":
                    first = f"Hello! I am {AGENT_NAME} in Cook Mode. What are we cooking today? Do you need today's brief or step-by-step recipe instructions?"
                else:
                    first = f"Namaste! Main {AGENT_NAME} (Cook Mode). Aaj kya banana hai — aaj ka brief chahiye ya kisi recipe ke step-by-step nirdesh?"
                return self.say("assistant", first)
            else:
                if self.lang == "ta-IN":
                    first = (f"வணக்கம்! நான் {AGENT_NAME} — உங்கள் வீட்டு சமையலை திட்டமிட வந்துள்ளேன். "
                             f"வீட்டில் யார் யார் இருக்கிறார்கள், ஏதேனும் உணவு கட்டுப்பாடுகள் அல்லது அலர்ஜி உள்ளதா?")
                elif self.lang == "en-IN":
                    first = (f"Hello! I am {AGENT_NAME} — I will manage your household meals. "
                             f"Who all are in your family, and are there any diets or allergies?")
                else:
                    first = (f"Namaste! Main {AGENT_NAME} — tumhare ghar ka khana sambhalungi. "
                             f"Ghar me kaun kaun hai, aur koi parhez ya allergy?")
                return self.say("assistant", first)

        # Cook mode execution branch
        if self.mode == "cook":
            crep = self._cook_turn(low)
            if crep is not None:
                return self.say("assistant", crep)
            # Cook mode must never fall through to household intake!
            if self.lang == "ta-IN":
                return self.say("assistant", "நான் குக்கர் உதவியாளர் (Cook Mode). இன்றைய சமையல் பட்டியல் (brief), ஏதேனும் உணவின் செய்முறை விளக்கங்கள் (recipe steps), அல்லது பொருட்கள் தீர்ந்துவிட்டதா என சொல்லுங்கள்!")
            elif self.lang == "en-IN":
                return self.say("assistant", "Cook mode active. Tell me — do you need today's brief, step-by-step recipe instructions, or report an ingredient issue?")
            return self.say("assistant", "Cook mode me hu. Bolo — aaj ka brief chahiye, recipe steps aur samaan ki matra, ya koi samaan khatm hua?")

        # Household mode actions
        if UNDO_RE.search(low) and ("cart" in low or "order" in low or self.cart):
            r = self.call("undo", {})
            if self.lang == "ta-IN":
                return self.say("assistant", f"திரும்பப் பெறப்பட்டது. கார்ட் இப்போது ₹{r.get('total', self.total)}." if r["ok"] else "திரும்பப் பெற எதுவும் இல்லை.", [r])
            elif self.lang == "en-IN":
                return self.say("assistant", f"Undone. Cart is now ₹{r.get('total', self.total)}." if r["ok"] else "Nothing to undo.", [r])
            return self.say("assistant", f"Wapas le liya. Cart ab Rs.{r.get('total', self.total)}." if r["ok"] else "Undo ke liye kuch nahi hai.", [r])

        if WA_RE.search(low) and self.cart:
            r = self.call("send_whatsapp", {})
            msg = r.get("message", "")
            if self.lang == "ta-IN":
                return self.say("assistant", f"வாட்ஸ்அப்பில் அனுப்பப்பட்டது (சிமுலேஷன்). மொத்தம் ₹{self.total}. முழு பட்டியல்:\n{msg}", [r])
            elif self.lang == "en-IN":
                return self.say("assistant", f"Sent via WhatsApp (simulated). Total ₹{self.total}. Full list:\n{msg}", [r])
            return self.say("assistant", f"Bhej diya (simulated). Total Rs.{self.total}. Poori list:\n{msg}", [r])

        if ORDER_RE.search(low) or (CONFIRM_RE.search(low) and self.pending_confirm):
            if not self.cart:
                r = self.call("build_grocery_list", {})
                if not r["ok"]:
                    if self.lang == "ta-IN":
                        return self.say("assistant", "முதலில் உணவு திட்டம் உருவாக்க வேண்டும். வீட்டில் யார் யார் இருக்கிறார்கள்?", [r])
                    elif self.lang == "en-IN":
                        return self.say("assistant", "We need to create a meal plan first. Who all are in your family?", [r])
                    return self.say("assistant", "Pehle plan banana padega. Ghar me kaun kaun hai?", [r])
                self.pending_confirm = True
                prompt_text = " உறுதியாக ஆர்டர் செய்யவா?" if self.lang == "ta-IN" else (" Shall I confirm and place the order?" if self.lang == "en-IN" else " Pakka order karu?")
                return self.say("assistant", self._cart_summary() + prompt_text, [r])

            if CONFIRM_RE.search(low) or self.pending_confirm:
                self.confirmed = True
                self.pending_confirm = False
                r = self.call("place_order", {"confirm": True})
                if r["ok"]:
                    if self.lang == "ta-IN":
                        return self.say("assistant", f"ஆர்டர் செய்யப்பட்டது! ஆர்டர் எண் {r['order_id']}, {r['eta_min']} நிமிடங்களில் வந்துவிடும் (சிமுலேஷன்). சமையல்காரருக்கு உணவு திட்டம் பகிரப்படும்.", [r])
                    elif self.lang == "en-IN":
                        return self.say("assistant", f"Order placed successfully! ID {r['order_id']}, arriving in {r['eta_min']} mins (simulated). I will hand off the plan to the cook.", [r])
                    return self.say("assistant", f"Order ho gaya! ID {r['order_id']}, {r['eta_min']} min me aayega (simulated). Kal se cook ko plan de dungi.", [r])
                if self.lang == "ta-IN":
                    return self.say("assistant", "ஆர்டர் செய்ய முடியவில்லை — ஏதோ விவரம் விடுபட்டுள்ளது. என்னவென்று சொல்லுங்கள்?", [r])
                elif self.lang == "en-IN":
                    return self.say("assistant", "Order could not be placed — something is missing. What would you like to do?", [r])
                return self.say("assistant", "Order nahi hua — kuch missing hai. Batao?", [r])

            self.pending_confirm = True
            confirm_hint = " 'சரி' என்று சொல்லுங்கள்." if self.lang == "ta-IN" else (" Say 'yes' to confirm." if self.lang == "en-IN" else " 'Haan' bolo.")
            prompt_text = " உறுதியாக ஆர்டர் செய்யவா?" if self.lang == "ta-IN" else (" Shall I confirm and place the order?" if self.lang == "en-IN" else " Pakka order karu?")
            return self.say("assistant", self._cart_summary() + prompt_text + confirm_hint, [])

        if NONVEG_PLAN_RE.search(low):
            self.household.nonveg_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            self.constraints.nonveg_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            setattr(self.household, "nonveg_primary", True)
            for m in self.household.members:
                if m.diet not in ("jain", "vegan") and m.age_group in ("adult", "teen", "senior"):
                    m.diet = "nonveg"
            for m in self.constraints.members:
                if m.diet not in ("jain", "vegan") and m.age_group in ("adult", "teen", "senior"):
                    m.diet = "nonveg"
            if self.household.members and self.household.budget_inr is not None:
                self.plan = None
                self.presented_until = 0
                self.stage = "COLLECT"
                return self._maybe_generate()

        if SWAP_RE.search(low) and self.plan is not None:
            return self._do_swap(low)

        if EXPLAIN_RE.search(low) and self.plan is not None:
            return self._do_explain(low)

        if GROCERY_RE.search(low) and self.plan is not None:
            r = self.call("build_grocery_list", {})
            if not r["ok"]:
                return self.say("assistant", "மளிகைப் பட்டியல் தயாரிக்க முடியவில்லை." if self.lang == "ta-IN" else ("Could not build grocery list." if self.lang == "en-IN" else "List nahi bani."), [r])
            self.pending_confirm = False
            ask = " ஆர்டர் செய்யவா அல்லது வாட்ஸ்அப்பில் அனுப்பவா?" if self.lang == "ta-IN" else (" Should I place the order or send via WhatsApp?" if self.lang == "en-IN" else " Order karu ya WhatsApp pe bheju?")
            return self.say("assistant", self._cart_summary() + ask, [r])

        pm = PANTRY_RE.search(low)
        if pm and ("ghar" in low or "hai" in low or "irukku" in low or "veetula" in low):
            qty, uword, item = float(pm.group(1)), pm.group(2), pm.group(3)
            unit, _ = QTYMAP.get(uword, ("g", 1))
            if uword in ("kilo", "kg"):
                qty *= 1000
                unit = "g"
            if uword in ("litre", "l"):
                qty *= 1000
                unit = "ml"
            r = self.call("update_pantry", {"item": item, "qty": qty, "unit": unit})
            if self.lang == "ta-IN":
                return self.say("assistant", f"குறித்துக் கொண்டேன் — {item} {pm.group(1)} {uword}. வேறு ஏதேனும் உள்ளதா?", [r])
            elif self.lang == "en-IN":
                return self.say("assistant", f"Noted — {item} {pm.group(1)} {uword}. Anything else?", [r])
            return self.say("assistant", f"Note kar liya — {item} {pm.group(1)} {uword}. Aur kuch?", [r])

        if MORE_RE.search(low) and self.plan is not None:
            return self.say("assistant", self.present_days())

        if PLAN_RE.search(low) and self.household.members and self.plan is None:
            self.constraints = extract(t, self.constraints)
            self._sync_household()
            return self._maybe_generate()

        if CORRECT_RE.search(low):
            before = self.constraints.model_dump()
            self.constraints = extract(t, self.constraints)
            self._sync_household()
            diff = self._diff_constraints(before)
            if self.plan and self._members_changed(before):
                self.plan = None
                self.stage = "COLLECT"
                return self.say("assistant", f"Theek, samajh gayi — {diff} Plan dobara banau?")
            if self.plan is not None:
                return self.say("assistant", f"Theek — {diff} Grocery total isi hisab se banegi.")
            if self.household.members:
                return self.say("assistant", f"Theek — {diff} Ab plan banau?")
            return self.say("assistant", f"Theek — {diff}")

        # default: extract + steer
        self.constraints = extract(t, self.constraints)
        self._sync_household()

        if not self.household.members:
            if self.lang == "ta-IN":
                return self.say("assistant", "வீட்டில் யார் யார் இருக்கிறார்கள்? பெயர், வயது, மற்றும் உணவு கட்டுப்பாடுகள் அல்லது அலர்ஜி ஏதேனும் உள்ளதா?")
            elif self.lang == "en-IN":
                return self.say("assistant", "Who all are in your family? Please share names, age, and any diets or allergies.")
            return self.say("assistant", "Ghar me kaun kaun khata hai? Naam, umar, aur koi parhez/allergy batao.")

        if self.household.budget_inr is None:
            if self.lang == "ta-IN":
                return self.say("assistant", "சரி. வார மளிகை பட்ஜெட் எவ்வளவு வைக்கலாம்?")
            elif self.lang == "en-IN":
                return self.say("assistant", "Got it. What should I set as your weekly grocery budget?")
            return self.say("assistant", "Theek. Hafte ka grocery budget kitna rakhu?")

        if self.plan is None:
            return self._maybe_generate()

        if self.lang == "ta-IN":
            return self.say("assistant", "புரிந்தது. உணவு திட்டம் தயார் — 'அடுத்து' என்று சொன்னால் அடுத்த நாட்களை கூறுகிறேன், அல்லது ஏதேனும் மாற்ற வேண்டுமா?")
        elif self.lang == "en-IN":
            return self.say("assistant", "Understood. The plan is ready — say 'next' to hear more, or let me know if you want any changes.")
        return self.say("assistant", "Samajh gayi. Plan ready hai — 'aur' bolo to aage sunau, ya koi change?")

    # -- sub-flows --
    def _sync_household(self) -> None:
        names = {m.name for m in self.household.members}
        for m in self.constraints.members:
            if m.name not in names and m.name not in ("Member1", "GuestNote"):
                self.household.members.append(m)
            elif m.name == "GuestNote":
                pass  # handled via guests intent
        if self.constraints.budget_inr is not None:
            self.household.budget_inr = self.constraints.budget_inr
        if self.constraints.days_to_plan != self.days_to_plan:
            self.days_to_plan = self.constraints.days_to_plan
        if self.constraints.nonveg_days:
            self.household.nonveg_days = sorted(set(self.household.nonveg_days) | set(self.constraints.nonveg_days))
        for m in self.constraints.members:
            for h in self.household.members:
                if h.name == m.name:
                    h.fasting_days = sorted(set(h.fasting_days) | set(m.fasting_days))
                    h.allergies = sorted(set(h.allergies) | set(m.allergies))
                    h.health_notes = sorted(set(h.health_notes) | set(m.health_notes))
                    if m.diet != "veg" or h.diet == "veg":
                        h.diet = m.diet
        if any(m.diet == "nonveg" for m in self.household.members) and not self.household.nonveg_days:
            self.household.nonveg_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        nv_c = sum(1 for m in self.household.members if m.diet == "nonveg")
        veg_c = sum(1 for m in self.household.members if m.diet in ("veg", "jain", "vegan"))
        adult_nv = sum(1 for m in self.household.members if m.age_group == "adult" and m.diet == "nonveg")
        adult_all = sum(1 for m in self.household.members if m.age_group == "adult")
        if (nv_c > veg_c) or (adult_all > 0 and adult_nv == adult_all and nv_c > 0):
            setattr(self.household, "nonveg_primary", True)

    @staticmethod
    def _real_members(d: dict | HouseholdConstraints) -> list[str]:
        ms = d["members"] if isinstance(d, dict) else [m.model_dump() for m in d.members]
        return sorted(m["name"] for m in ms if m["name"] not in ("Member1", "GuestNote"))

    def _diff_constraints(self, before: dict) -> str:
        bits = []
        if before.get("budget_inr") != self.constraints.budget_inr:
            bits.append(f"budget Rs.{self.constraints.budget_inr}")
        if before.get("days_to_plan") != self.constraints.days_to_plan:
            bits.append(f"{self.constraints.days_to_plan} din")
        bn, an = len(self._real_members(before)), len(self._real_members(self.constraints))
        if an > bn:
            bits.append(f"{an - bn} member aur")
        return ", ".join(bits) or "note kar liya"

    def _members_changed(self, before: dict) -> bool:
        return self._real_members(before) != self._real_members(self.constraints)

    def _maybe_generate(self) -> str:
        r = self.call("generate_plan", {"days": self.days_to_plan, "seed": CONFIG.planner_seed})
        if not r["ok"]:
            if self.lang == "ta-IN":
                return self.say("assistant", "உணவு திட்டத்தை உருவாக்க முடியவில்லை.", [r])
            elif self.lang == "en-IN":
                return self.say("assistant", "Could not generate the plan.", [r])
            return self.say("assistant", "Plan nahi ban paya.", [r])

        self.stage = "NEGOTIATE"
        c = ""
        if r["conflicts"]:
            if self.lang == "ta-IN":
                c = f" ஒரு முரண்பாடு உள்ளது: {r['conflicts'][0]}."
            elif self.lang == "en-IN":
                c = f" One conflict noticed: {r['conflicts'][0]}."
            else:
                c = f" Ek conflict hai: {r['conflicts'][0]}."

        if self.lang == "ta-IN":
            msg = f"உணவு திட்டம் தயார் — {r['days']} நாட்கள், {r['meals']} வேளை உணவுகள்.{c} முதல் 2 நாட்களை கேளுங்கள்: " + self.present_days()
        elif self.lang == "en-IN":
            msg = f"Plan ready — {r['days']} days, {r['meals']} meals.{c} Here are the first 2 days: " + self.present_days()
        else:
            msg = f"Plan ready — {r['days']} din, {r['meals']} meals.{c} Pehle 2 din suno: " + self.present_days()
        return self.say("assistant", msg, [r])

    def _find_day_slot(self, low: str) -> tuple[str | None, str | None]:
        day = next((v for k, v in T.DAYMAP.items() if k in low), None)
        if day is None:
            for d in WEEK:
                if d.lower() in low:
                    day = d
                    break
        slot = next((v for k, v in T.SLOTMAP.items() if re.search(rf"\b{k}\b", low)), None)
        return day, slot

    def _do_swap(self, low: str) -> str:
        day, slot = self._find_day_slot(low)
        if day is None:
            if self.lang == "ta-IN":
                return self.say("assistant", "எந்த நாள்? (திங்கள், செவ்வாய்...)")
            elif self.lang == "en-IN":
                return self.say("assistant", "Which day? (Monday, Tuesday...)")
            return self.say("assistant", "Kaun se din? (Monday, Tuesday...)")
        if slot is None:
            if self.lang == "ta-IN":
                return self.say("assistant", "காலை, மதியம் அல்லது இரவா?")
            elif self.lang == "en-IN":
                return self.say("assistant", "Breakfast, lunch, or dinner?")
            return self.say("assistant", "Nashta, dopahar ya raat?")

        after = low.split("nahi")[-1] if "nahi" in low else (low.split("பதில்")[-1] if "பதில்" in low else low)
        rid = T.match_dish(after, self.by_id)
        want = self.by_id[rid].name if rid else ""
        r = self.call("swap_meal", {"day": day, "slot": slot, "new_dish": want})
        if not r["ok"]:
            if self.lang == "ta-IN":
                return self.say("assistant", f"மாற்ற முடியவில்லை — {r.get('error')}", [r])
            elif self.lang == "en-IN":
                return self.say("assistant", f"Swap could not be made — {r.get('error')}", [r])
            return self.say("assistant", f"Swap nahi hua — {r['error']}", [r])

        self.last_meal = (day, slot)
        ad = "".join(f" ({a['member']} ke liye alag)" for a in r["adaptations"]) if r["adaptations"] else ""
        if self.lang == "ta-IN":
            return self.say("assistant", f"மாற்றப்பட்டது — {day} {slot}: {r['old']}-க்கு பதிலாக {r['new']}. வேறு ஏதேனும் மாற்ற வேண்டுமா?", [r])
        elif self.lang == "en-IN":
            return self.say("assistant", f"Done — {day} {slot}: {r['new']} instead of {r['old']}. Anything else?", [r])
        return self.say("assistant", f"Done — {day} {slot}: {r['old']} ki jagah {r['new']}.{ad} Kuch aur?", [r])

    def _do_explain(self, low: str) -> str:
        if self.last_meal and not self._find_day_slot(low)[0]:
            day, slot = self.last_meal
        else:
            day, slot = self._find_day_slot(low)
            if day is None or slot is None:
                if self.lang == "ta-IN":
                    return self.say("assistant", "எந்த உணவை பற்றி விளக்க வேண்டும்? நாள் மற்றும் நேரத்தை சொல்லுங்கள்.")
                elif self.lang == "en-IN":
                    return self.say("assistant", "Which meal should I explain? Please tell me the day and slot.")
                return self.say("assistant", "Kaun sa meal samjhau? Din aur time batao.")

        r = self.call("explain_meal", {"day": day, "slot": slot})
        if not r["ok"]:
            return self.say("assistant", "Woh meal mila nahi." if self.lang != "ta-IN" else "அந்த உணவு கிடைக்கவில்லை.", [r])
        why = "; ".join(r["why"][:2]) or "sab ke liye safe aur simple"
        return self.say("assistant", f"{r['dish']} — {why}.", [r])

    # -- cook mode: short, direct, quantities repeated, step-by-step instructions --
    def _cook_turn(self, low: str) -> str | None:
        from app.engine import kitchen as K

        is_step_req = bool(re.search(
            r"step|recipe|detail|ingredient|how to (make|cook)|method|vidhi|படி|படிகள்|ஸ்டெப்|ஸ்டெப்ஸ்|செய்முறை|எப்படி செய்யணும்|எப்படி சமைக்கணும்|பொருட்கள்|அளவுகள்|எழுதி|எவ்வளோ|போடணும்|விவரம்|विधि|रेसिपी|स्टेप|बनाने का तरीका",
            low
        ))
        is_brief_req = bool(re.search(
            r"brief|aaj ka|aaj kya|kya banana|samayal|samaik|enna panna|enna samayal|இன்னைக்கு|இன்று|சமைக்க|சமையல்|பண்ணனும்|என்ன செய்ய|என்ன சமையல்|आज क्या",
            low
        ))

        # 1. Step-by-Step Recipe Instructions with exact ingredients and quantities
        if is_step_req:
            # Check if a specific recipe was requested
            matched_rid = T.match_dish(low, self.by_id)
            if not matched_rid:
                for rid, rec in self.by_id.items():
                    rname = rec.name.lower()
                    if rid in low or rname in low or any(word in low for word in rname.split() if len(word) > 3):
                        matched_rid = rid
                        break

            if matched_rid and matched_rid in self.by_id:
                rec = self.by_id[matched_rid]
                servings = len(self.household.members) if self.household.members else 4
                adaptations = []
                if self.plan:
                    for d in self.plan.days:
                        for m in d.meals:
                            if m.recipe_id == matched_rid and m.adaptations:
                                adaptations.extend(m.adaptations)
                return format_recipe_instructions(rec, servings=servings, lang=self.lang, adaptations=adaptations)

            # If no dish was specifically named, check if meal plan exists and pick current day's meal
            if self.plan:
                day, slot = self._find_day_slot(low)
                wd = day or self.cook_weekday()
                p_day = K.get_day(self.plan, wd)
                if p_day and p_day.meals:
                    target_meal = p_day.meals[0]
                    if slot:
                        for m in p_day.meals:
                            if m.slot == slot:
                                target_meal = m
                                break
                    rec = self.by_id.get(target_meal.recipe_id)
                    if rec:
                        servings = target_meal.servings or (len(self.household.members) if self.household.members else 4)
                        header = f"[{wd} {target_meal.slot.capitalize()}]\n"
                        return header + format_recipe_instructions(rec, servings=servings, lang=self.lang, adaptations=target_meal.adaptations)

            # If no specific dish matched and no plan exists yet:
            if self.lang == "ta-IN":
                return "எந்த உணவின் செய்முறை மற்றும் பொருட்கள் விவரம் வேண்டும்? (உதாரணமாக: Kanda Poha, Vegetable Upma, Dal Tadka, Aloo Paratha, Idli Sambar, Masala Dosa, Paneer Bhurji). உணவின் பெயரைச் சொன்னால், தேவையான பொருட்கள், அளவுகள் மற்றும் செய்முறையை படி படியாக கூறுகிறேன்!"
            elif self.lang == "en-IN":
                return "Which recipe would you like step-by-step instructions for? (For example: Kanda Poha, Vegetable Upma, Dal Tadka, Aloo Paratha, Idli Sambar, Masala Dosa, Paneer Bhurji). Tell me the dish name and I will provide the ingredients, exact quantities, and step-by-step cooking process!"
            return "Aapko kaun si recipe ke step-by-step nirdesh chahiye? (Jaise: Kanda Poha, Vegetable Upma, Dal Tadka, Aloo Paratha, Idli Sambar, Masala Dosa). Dish ka naam bataiye, main saaman, matra aur poori vidhi bataungi!"

        # 2. Daily Brief Request
        if is_brief_req:
            if self.plan is None:
                if self.lang == "ta-IN":
                    return "இன்னும் வாராந்திர உணவு திட்டம் உருவாக்கப்படவில்லை. ஆனால் நீங்கள் சமைக்க விரும்பும் உணவின் பெயரைச் சொன்னால் (உதாரணம்: Kanda Poha, Upma, Dal Tadka), அதன் செய்முறை மற்றும் அளவுகளை உடனே தருகிறேன்!"
                elif self.lang == "en-IN":
                    return "No weekly meal plan has been created yet. But tell me any dish you want to cook (e.g. Kanda Poha, Upma, Dal Tadka) and I will provide the recipe and cooking instructions immediately!"
                return "Abhi weekly meal plan taiyaar nahi hai. Par aap jo dish banana chahte hain uska naam bataiye (jaise Poha, Upma, Dal Tadka), main turant vidhi aur samaan bata dungi!"

            day, _s = self._find_day_slot(low)
            wd = day or self.cook_weekday()
            r = self.call("get_daily_brief", {"weekday": wd or ""})
            if not r["ok"]:
                return "Brief kidaikkala." if self.lang == "ta-IN" else "Brief nahi mil paya."

            rem = f" Check: {'; '.join(r['reminders'][:2])}." if r["reminders"] else ""
            if self.lang == "ta-IN":
                return (f"இன்று {r['weekday']}. முதலில் {r['start_first']} தொடங்குங்கள். "
                        + " பிறகு ".join(r["steps"][:4]) + "." + rem + " செய்முறை விளக்கங்கள் தேவைப்பட்டால் உணவின் பெயரைச் சொல்லுங்கள்.")
            elif self.lang == "en-IN":
                return (f"Today is {r['weekday']}. Start first with {r['start_first']}. "
                        + " Then ".join(r["steps"][:4]) + "." + rem + " To hear full step-by-step instructions with items and quantities, just tell me the dish name.")
            return (f"Aaj {r['weekday']}. Sabse pehle {r['start_first']} shuru karo. "
                    + " Phir ".join(r["steps"][:4]) + "." + rem + " Step-by-step vidhi ke liye dish ka naam bolo.")

        # 3. Advance prep / Lookahead
        if re.search(r"kal ki|taiyari|pehle se|advance|naalaikku|thayarippu|நாளை|நாளைக்கு|முன்னாடி|தயாரிப்பு", low):
            if self.plan is None:
                return "நாளைக்கு எந்த தயாரிப்பும் தேவையில்லை." if self.lang == "ta-IN" else "No advance prep needed."
            la = K.evening_lookahead(self.plan, self.cook_weekday(), self.by_id)
            if not la.get("tasks"):
                if self.lang == "ta-IN":
                    return f"நாளைக்கு ({la.get('next')}) எந்த தயாரிப்பும் தேவையில்லை. நிம்மதியாக இருங்கள்."
                elif self.lang == "en-IN":
                    return f"No advance prep needed for tomorrow ({la.get('next')}). Take rest."
                return f"Kal ({la.get('next')}) ke liye koi taiyari nahi. Aaram karo."

            if self.lang == "ta-IN":
                return f"நாளைக்கு ({la['next']}): " + " பிறகு ".join(la["tasks"][:3]) + "."
            elif self.lang == "en-IN":
                return f"Tomorrow ({la['next']}): " + " Then ".join(la["tasks"][:3]) + "."
            return f"Kal {la['next']}: " + " Phir ".join(la["tasks"][:3]) + "."

        # 4. Cook leave / disruption
        if re.search(r"chhutti|leave|aaram|thaka|tabiyat|லீவு|விடுமுறை|உடம்பு சரியில்லை|முடியல|ரெஸ்ட்", low):
            day, _s = self._find_day_slot(low)
            r = self.call("report_disruption",
                          {"kind": "cook_leave", "detail": low, "day": day or "", "slot": ""})
            dishes = "; ".join(f"{s['slot']} me {s['new']}" for s in r.get("swapped", []))
            if self.lang == "ta-IN":
                return f"இன்று ஓய்வெடுங்கள். இன்று எளிமையான சமையல்: {dishes or 'எளிய உணவு'}. அவ்வளவுதான்." if r["ok"] else "புரியவில்லை."
            elif self.lang == "en-IN":
                return f"Take rest today. Today's meals simplified: {dishes or 'simple meals'}." if r["ok"] else "Could not process."
            return f"Aaram karo. Aaj sirf: {dishes or 'simple khana'}. Bas." if r["ok"] else "Samajh nahi aaya."

        # 5. Extra guests
        if re.search(r"mehman|guest|log aa|விருந்தினர்|கெஸ்ட்|ஆட்கள் வராங்க|பேர் வராங்க", low):
            day, slot = self._find_day_slot(low)
            m = re.search(r"(\d+)", low)
            r = self.call("report_disruption",
                          {"kind": "extra_guests", "detail": f"{m.group(1)} guests" if m else "2 guests",
                           "day": day or "", "slot": slot or "dinner"})
            if not r["ok"]:
                return "விருந்தினர் விவரத்தை பதிவு செய்ய முடியவில்லை." if self.lang == "ta-IN" else ("Could not record guest details." if self.lang == "en-IN" else "Mehman note nahi hua.")
            tot = r.get("total_servings", [])
            tot_s = tot[0] if len(tot) == 1 else tot
            if self.lang == "ta-IN":
                return (f"சரி. {r['slot']}-ல் {r['added_servings']} கூடுதல் நபர்கள் — மொத்தம் {tot_s} அளவுகள், சரியா? "
                        f"தேவையான கூடுதல் பொருட்கள் அடுத்த மளிகைப் பட்டியலில் சேர்க்கப்பட்டுள்ளது.")
            elif self.lang == "en-IN":
                return (f"Noted. {r['added_servings']} extra servings for {r['slot']} — total {tot_s} portions, okay? "
                        f"Shortfalls added to the next grocery list.")
            return (f"Theek. {r['slot']} me {r['added_servings']} extra — total {tot_s}, {tot_s} theek? "
                    f"Samaan agli list me jod diya.")

        # 6. Equipment breakdown
        if re.search(r"kharab|toot|cooker kharab|gas|ரிப்பேர்|உடைஞ்சிடுச்சு|வேலை செய்யல|குக்கர் பிரச்சனை|கேஸ் தீர்ந்து", low):
            day, _s = self._find_day_slot(low)
            eq = "cooker" if any(k in low for k in ["cooker", "pressure", "குக்கர்"]) else "stove"
            r = self.call("report_disruption",
                          {"kind": "equipment_broken", "detail": eq, "day": day or "", "slot": ""})
            if not r["ok"] or not r.get("swapped"):
                return r.get("note", "புரியவில்லை." if self.lang == "ta-IN" else "Samajh nahi aaya.")
            s = r["swapped"][0]
            if self.lang == "ta-IN":
                return f"சரி. {s['slot']}-ல் {s['old']}-க்கு பதிலாக {s['new']} ({s['mins']} நிமிடங்கள்). சரியா?"
            elif self.lang == "en-IN":
                return f"Got it. Swapped {s['old']} for {s['new']} ({s['mins']} mins) in {s['slot']}. Okay?"
            return f"Theek. {s['slot']} me {s['old']} ki jagah {s['new']} ({s['mins']} min). Theek?"

        # 7. Missing ingredient / shortfall
        if re.search(r"khatm|nahi hai|nahi aaya|galat item|missing|kam hai|தீர்ந்துடுச்சு|இல்லை|பத்தல|முடிஞ்சுது", low):
            day, _s = self._find_day_slot(low)
            item = next((k for k in sorted(self.catalog, key=len, reverse=True) if k in low), "")
            if not item:
                TAMIL_ITEM_MAP = {
                    "தக்காளி": "tomato", "thakkali": "tomato",
                    "வெங்காயம்": "onion", "vengayam": "onion",
                    "உருளைக்கிழங்கு": "potato", "urulaikizhangu": "potato",
                    "பால்": "milk", "paal": "milk",
                    "தயிர்": "curd", "thayir": "curd",
                    "பருப்பு": "toor_dal", "paruppu": "toor_dal",
                    "எண்ணெய்": "oil", "ennai": "oil",
                }
                for tk, ik in TAMIL_ITEM_MAP.items():
                    if tk in low:
                        item = ik
                        break
            if not item:
                if self.lang == "ta-IN":
                    return "எந்த பொருள் தீர்ந்துவிட்டது? பொருளின் பெயரைச் சொல்லுங்கள்."
                elif self.lang == "en-IN":
                    return "Which ingredient is missing? Please tell me the name."
                return "Kaun si cheez khatm? Naam bolo."

            r = self.call("report_disruption",
                          {"kind": "missing_ingredient", "detail": item, "day": day or "", "slot": ""})
            if not r["ok"]:
                return r.get("error", f"{item} ka jugaad nahi mila — bazaar se lao.")
            if not r.get("swapped"):
                return r.get("note", "சரி." if self.lang == "ta-IN" else "Theek.")
            s = r["swapped"][0]
            extra = f" {item} agli list me likh diya." if r.get("shortfall") else ""
            if self.lang == "ta-IN":
                extra_ta = f" {item} அடுத்த மளிகைப் பட்டியலில் சேர்க்கப்பட்டது." if r.get("shortfall") else ""
                return f"சரி. {s['slot']}-ல் {s['old']}-க்கு பதிலாக {s['new']} ({s['mins']} நிமிடங்கள்). சரியா?{extra_ta}"
            elif self.lang == "en-IN":
                extra_en = f" {item} added to the next grocery list." if r.get("shortfall") else ""
                return f"Got it. Swapped {s['old']} for {s['new']} ({s['mins']} mins) in {s['slot']}. Okay?{extra_en}"
            return f"Theek. {s['slot']} me {s['old']} ki jagah {s['new']} ({s['mins']} min). Theek?{extra}"

        # 8. Log cooked meal
        if re.search(r"bana diya|ban gaya|ho gaya|taiyaar|nahi bana|skip|சமைச்சாச்சு|செஞ்சாச்சு|பண்ணியாச்சு|ரெடி|ஆகல|செய்யல|samachachu|senjachu|paniyachu", low):
            _d, slot = self._find_day_slot(low)
            if slot is None:
                if self.lang == "ta-IN":
                    return "எந்த வேளை உணவு — காலை, மதியம் அல்லது இரவா?"
                elif self.lang == "en-IN":
                    return "Which meal — breakfast, lunch, or dinner?"
                return "Kaun sa — dopahar ya raat?"

            status = "skipped" if re.search(r"nahi bana|skip|ஆகல|செய்யல", low) else "cooked"
            note = ""
            for sep in [",", " par ", " lekin ", " but ", " aana "]:
                if sep in low:
                    note = low.split(sep, 1)[1].strip()
                    break
            r = self.call("log_cooked", {"slot": slot, "status": status, "note": note})
            tail = " Agli baar dhyan rakhungi." if r.get("taste_note") else ""
            if self.lang == "ta-IN":
                tail_ta = " அடுத்த முறை கவனித்துக் கொள்கிறேன்." if r.get("taste_note") else ""
                return f"குறித்துக் கொண்டேன் — {r.get('dish', slot)} {status}." + tail_ta
            elif self.lang == "en-IN":
                tail_en = " I will keep that in mind next time." if r.get("taste_note") else ""
                return f"Logged — {r.get('dish', slot)} {status}." + tail_en
            return f"Note kar liya — {r.get('dish', slot)} {status}." + tail

        # Default cook mode fallback: stay in cook register
        if self.lang == "ta-IN":
            return "நான் குக்கர் உதவியாளர் (Cook Mode). சொல்லுங்கள் — இன்றைய சமையல் பட்டியல் (brief) வேண்டுமா, ஏதேனும் உணவின் செய்முறை விளக்கங்கள் (recipe steps) வேண்டுமா, அல்லது பொருட்கள் ஏதேனும் தீர்ந்துவிட்டதா?"
        elif self.lang == "en-IN":
            return "Cook mode active. Tell me — do you need today's brief, step-by-step recipe instructions with quantities, or report an ingredient issue?"
        return "Cook mode me hu. Bolo — aaj ka brief chahiye, recipe steps, ya koi samaan khatm hua?"

    def _cart_summary(self) -> str:
        miss = f" {len(self.missing)} cheez out of stock hai ({', '.join(self.missing[:3])})." if self.missing else ""
        subs = [f"{ln['item']}" for ln in self.cart if ln.get("substituted")]
        sub = f" Substitute: {', '.join(subs)}." if subs else ""
        b = f" Budget Rs.{self.household.budget_inr}." if self.household.budget_inr else ""
        return f"List ready — {len(self.cart)} items, total Rs.{self.total}.{b}{miss}{sub}"

    def save_transcript(self, base: str) -> tuple[str, str]:
        jl = base + ".jsonl"
        md = base + ".md"
        with open(jl, "w", encoding="utf-8") as f:
            for e in self.transcript:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        with open(md, "w", encoding="utf-8") as f:
            for e in self.transcript:
                who = {"user": "User", "assistant": AGENT_NAME, "tool": "Tool"}.get(e["role"], e["role"])
                f.write(f"**{who}:** {e['text']}\n\n")
        return jl, md
