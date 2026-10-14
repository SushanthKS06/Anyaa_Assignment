"""Rasoi — the kitchen manager. One shared brain, two registers.

NAME: Rasoi (means 'kitchen' — Indian kitchen manager).
ROLE: Warm, capable, respectful kitchen manager who runs household meals
and assists the cook with clear, accurate cooking instructions.

LANGUAGE DISCIPLINE:
- Tamil (ta-IN): Output in natural Tamil script. No Hindi words.
- English (en-IN): Output in clean, natural English. No Hindi words.
- Hindi (hi-IN): Output in warm, natural Hindi / Hinglish.
"""
from __future__ import annotations

import re

AGENT_NAME = "Rasoi"
MAX_ITEMS_PER_TURN = 3
HOUSEHOLD_STYLE = "warm, collaborative, 1-2 short sentences, one question at a time"
COOK_STYLE = "simple, direct, respectful, repeat quantities back, step-by-step"

HOUSEHOLD_SYSTEM = """You are Rasoi, a warm, capable, caring Indian kitchen manager.
STRICT LANGUAGE DISCIPLINE:
- When user speaks Tamil (ta-IN): You MUST reply ONLY in Tamil script. Never use any Hindi words (no 'din', 'aur', 'theek', 'haan', 'batao', 'suno'). Keep Tamil warm and natural.
- When user speaks English (en-IN): You MUST reply ONLY in natural English. Never use any Hindi words.
- When user speaks Hindi (hi-IN): Reply in warm, natural Hindi / Hinglish.

Rules: Keep responses conversational and concise (1-2 short sentences per turn, unless presenting full meal plans). One question at a time. Repeat numbers back. You never say 'as an AI'. You negotiate kindly: elders' health first, kids get a slot. Safety (allergies, fasting, Jain rules) is non-negotiable. You verbalize what the tools return — you never invent dishes, prices, or quantities. If a tool reports a conflict, explain it plainly."""

COOK_SYSTEM = """You are Rasoi speaking to the cook in the kitchen.
STRICT LANGUAGE DISCIPLINE:
- When the cook speaks Tamil (ta-IN): You MUST reply ONLY in Tamil script. Never use any Hindi words.
- When the cook speaks English (en-IN): You MUST reply ONLY in natural English.
- When the cook speaks Hindi (hi-IN): Reply in simple, respectful Hindi / Hinglish.

CRITICAL RULES FOR COOK MODE:
- You are in COOK MODE. DO NOT ask household intake questions (do NOT ask who eats in the house, do NOT ask for weekly grocery budget).
- When asked for a recipe or step-by-step instructions:
  1. Clearly list all ITEMS USED and their EXACT QUANTITIES (e.g. poha: 200g, onions: 120g, oil: 40ml).
  2. Clearly explain the COOKING PROCESS STEP-BY-STEP (Step 1, Step 2, Step 3, etc.).
  3. Mention any special adaptations or notes (e.g. softer food for toddler, no peanuts for allergy).
- Keep instructions practical, clear, and direct. Repeat quantities back.
- Verbalize tool results and recipe steps accurately without inventing ingredients or prices."""


def localize_reply(text: str, lang: str) -> str:
    """Fallback localizer for deterministic replies when live LLM is offline or in mock mode."""
    if lang == "hi-IN" or not lang:
        return text

    if lang == "ta-IN":
        # Greetings
        if any(p in text for p in ["Main Rasoi — tumhare ghar", "ungal veetu samayalai", "veetu samayalai plan panna"]):
            return "வணக்கம்! நான் Rasoi — உங்கள் வீட்டு சமையலை திட்டமிட வந்துள்ளேன். வீட்டில் யார் யார் இருக்கிறார்கள், ஏதேனும் உணவு கட்டுப்பாடுகள் அல்லது அலர்ஜி உள்ளதா?"
        if "Sun rahi hu — bolo?" in text:
            return "கேட்டுக் கொண்டிருக்கிறேன் — சொல்லுங்கள்?"
        if "Ghar me kaun kaun khata hai?" in text:
            return "வீட்டில் யார் யார் இருக்கிறார்கள்? பெயர், வயது, மற்றும் உணவு கட்டுப்பாடுகள் அல்லது அலர்ஜி ஏதேனும் உள்ளதா?"
        if "Hafte ka grocery budget kitna rakhu?" in text:
            return "சரி. வார மளிகை பட்ஜெட் எவ்வளவு வைக்கலாம்?"
        if "Samajh gayi. Plan ready hai" in text or "Purinjidhu. Plan ready" in text:
            return "புரிந்தது. உணவு திட்டம் தயார் — 'அடுத்து' என்று சொன்னால் அடுத்த நாட்களை கூறுகிறேன், அல்லது ஏதேனும் மாற்ற வேண்டுமா?"
        if "Kaun se din?" in text:
            return "எந்த நாள்? (திங்கள், செவ்வாய்...)"
        if "Nashta, dopahar ya raat?" in text:
            return "காலை, மதியம் அல்லது இரவா?"
        if "Kaun sa meal samjhau?" in text:
            return "எந்த வேளை உணவை பற்றி விளக்க வேண்டும்? நாள் மற்றும் நேரத்தை சொல்லுங்கள்."
        if "Woh meal mila nahi." in text:
            return "அந்த உணவு பட்டியலில் இல்லை."
        if "List nahi bani." in text:
            return "மளிகைப் பட்டியல் தயாரிக்க முடியவில்லை."
        if "Plan nahi ban paya." in text:
            return "உணவு திட்டத்தை உருவாக்க முடியவில்லை."
        if "Undo ke liye kuch nahi hai." in text:
            return "திரும்பப் பெற எதுவும் இல்லை."
        if "Wapas le liya." in text:
            return text.replace("Wapas le liya. Cart ab", "திரும்பப் பெறப்பட்டது. கார்ட் இப்போது").replace("Rs.", "₹")
        if "Plan ready —" in text:
            t = text
            t = re.sub(r"Plan ready — (\d+) din, (\d+) meals\.", r"உணவு திட்டம் தயார் — \1 நாட்கள், \2 வேளை உணவுகள்.", t)
            t = t.replace("Pehle 2 din suno:", "முதல் 2 நாட்களை கேளுங்கள்:")
            t = t.replace("Aur? (aur bolo)", "அடுத்து என்ன? ('அடுத்து' என்று சொல்லுங்கள்)")
            t = t.replace("Aur?", "அடுத்து என்ன?")
            t = t.replace("Bas, poora hafta done.", "அவ்வளவுதான், முழு வாரமும் திட்டமிடப்பட்டது.")
            t = t.replace("breakfast", "காலை").replace("lunch", "மதியம்").replace("dinner", "இரவு")
            t = t.replace("Mon", "திங்கள்").replace("Tue", "செவ்வாய்").replace("Wed", "புதன்").replace("Thu", "வியாழன்").replace("Fri", "வெள்ளி").replace("Sat", "சனி").replace("Sun", "ஞாயிறு")
            t = re.sub(r"\((\w+) ke liye vrat plate\)", r"(\1-க்கு விரத உணவு)", t)
            t = re.sub(r"\((\w+) ke liye alag\)", r"(\1-க்கு தனி உணவு)", t)
            return t
        if "List ready —" in text or "Cart ready:" in text:
            t = text
            t = re.sub(r"List ready — (\d+) items, total Rs\.(\d+(?:\.\d+)?)", r"மளிகைப் பட்டியல் தயார் — \1 பொருட்கள், மொத்தம் ₹\2", t)
            t = t.replace("Pakka order karu?", "உறுதியாக ஆர்டர் செய்யவா?")
            t = t.replace("'Haan' bolo.", "'சரி' என்று சொல்லுங்கள்.")
            t = t.replace("Order karu ya WhatsApp pe bheju?", "ஆர்டர் செய்யவா அல்லது வாட்ஸ்அப்பில் அனுப்பவா?")
            t = t.replace("cheez out of stock hai", "பொருட்கள் ஸ்டாக்கில் இல்லை")
            t = t.replace("Substitute:", "மாற்றுப் பொருள்:")
            t = t.replace("Budget Rs.", "பட்ஜெட் ₹")
            return t
        if "Order ho gaya!" in text:
            t = text
            t = t.replace("Order ho gaya!", "ஆர்டர் செய்யப்பட்டது!")
            t = re.sub(r"(\d+) min me aayega \(simulated\)\. Kal se cook ko plan de dungi\.", r"\1 நிமிடங்களில் வந்துவிடும் (சிமுலேஷன்). சமையல்காரருக்கு திட்டத்தை பகிர்வேன்.", t)
            return t
        if "Order nahi hua" in text:
            return "ஆர்டர் செய்ய முடியவில்லை — ஏதோ விவரம் விடுபட்டுள்ளது. என்னவென்று சொல்லுங்கள்?"
        if "Cook mode" in text and ("aaj kya banana hai" in text or "active" in text or "Brief" in text):
            return "குக் மோட் (Cook Mode). சொல்லுங்கள் — இன்னைக்கு என்ன சமையல் செய்ய வேண்டும்? இன்றைய சமையல் குறிப்பு (brief) வேண்டுமா அல்லது ஏதேனும் உணவின் செய்முறை விளக்கங்கள் தேவையா?"
        if "Household mode" in text:
            return "ஹவுஸ்ஹோல்ட் மோட் (Household Mode). சொல்லுங்கள் — உணவு திட்டம், மளிகைப் பட்டியல் அல்லது ஆர்டர் செய்ய வேண்டுமா?"
        if "Bhej diya (simulated)" in text:
            return text.replace("Bhej diya (simulated)", "வாட்ஸ்அப்பில் அனுப்பப்பட்டது (சிமுலேஷன்)").replace("Total Rs.", "மொத்தம் ₹").replace("Poori list:", "முழு பட்டியல்:")
        if "Done —" in text:
            t = text.replace("Done —", "மாற்றப்பட்டது —")
            t = t.replace("ki jagah", "பதிலாக")
            t = t.replace("Kuch aur?", "வேறு ஏதேனும் மாற்ற வேண்டுமா?")
            return t
        if "Note kar liya —" in text:
            return text.replace("Note kar liya —", "குறித்துக் கொண்டேன் —").replace("Aur kuch?", "வேறு ஏதேனும் உள்ளதா?")
        if "Aaram karo." in text:
            return text.replace("Aaram karo. Aaj sirf:", "இன்று ஓய்வெடுங்கள். இன்று மட்டும்:").replace("Bas.", "அவ்வளவுதான்.")
        if "Sabse pehle" in text or "Mudhalla" in text:
            t = text.replace("Aaj", "இன்று").replace("Sabse pehle", "முதலில்").replace("shuru karo. Phir", "தொடங்குங்கள். பிறகு")
            return t
        return text

    if lang == "en-IN":
        # English translations
        if any(p in text for p in ["Main Rasoi — tumhare ghar", "ungal veetu samayalai", "household meals"]):
            return "Hello! I am Rasoi, your household meal manager. Who all are in your family, and are there any diets or allergies?"
        if "Sun rahi hu — bolo?" in text:
            return "I am listening — please go ahead."
        if "Ghar me kaun kaun khata hai?" in text:
            return "Who all eat in your home? Please share names, age, and any diets or allergies."
        if "Hafte ka grocery budget kitna rakhu?" in text:
            return "Got it. What should I set as your weekly grocery budget?"
        if "Samajh gayi. Plan ready hai" in text or "Purinjidhu. Plan ready" in text:
            return "Understood. The plan is ready — say 'next' to hear more, or let me know if you want any changes."
        if "Kaun se din?" in text:
            return "Which day? (Monday, Tuesday...)"
        if "Nashta, dopahar ya raat?" in text:
            return "Breakfast, lunch, or dinner?"
        if "Kaun sa meal samjhau?" in text:
            return "Which meal should I explain? Please tell me the day and slot."
        if "Woh meal mila nahi." in text:
            return "That meal could not be found."
        if "List nahi bani." in text:
            return "Could not build the grocery list."
        if "Plan nahi ban paya." in text:
            return "Could not generate the plan."
        if "Undo ke liye kuch nahi hai." in text:
            return "Nothing to undo."
        if "Wapas le liya." in text:
            return text.replace("Wapas le liya. Cart ab", "Undone. Cart is now").replace("Rs.", "₹")
        if "Plan ready —" in text:
            t = text
            t = re.sub(r"Plan ready — (\d+) din, (\d+) meals\.", r"Plan ready — \1 days, \2 meals.", t)
            t = t.replace("Pehle 2 din suno:", "Here are the first 2 days:")
            t = t.replace("Aur? (aur bolo)", "What next? (say 'next')")
            t = t.replace("Aur?", "What next?")
            t = t.replace("Bas, poora hafta done.", "That's all, full week planned.")
            t = re.sub(r"\((\w+) ke liye vrat plate\)", r"(\1: fasting plate)", t)
            t = re.sub(r"\((\w+) ke liye alag\)", r"(\1: separate dish)", t)
            return t
        if "List ready —" in text or "Cart ready:" in text:
            t = text
            t = re.sub(r"List ready — (\d+) items, total Rs\.(\d+(?:\.\d+)?)", r"Grocery list ready — \1 items, total ₹\2", t)
            t = t.replace("Pakka order karu?", "Shall I confirm and place the order?")
            t = t.replace("'Haan' bolo.", "Say 'Yes' to confirm.")
            t = t.replace("Order karu ya WhatsApp pe bheju?", "Should I place the order or send via WhatsApp?")
            t = t.replace("cheez out of stock hai", "items out of stock")
            t = t.replace("Substitute:", "Substitutes:")
            t = t.replace("Budget Rs.", "Budget ₹")
            return t
        if "Order ho gaya!" in text:
            t = text
            t = t.replace("Order ho gaya!", "Order placed successfully!")
            t = re.sub(r"(\d+) min me aayega \(simulated\)\. Kal se cook ko plan de dungi\.", r"Arriving in \1 mins (simulated). I will hand off the plan to the cook.", t)
            return t
        if "Order nahi hua" in text:
            return "Order could not be placed — something is missing. What would you like to do?"
        if "Cook mode" in text and ("aaj kya banana hai" in text or "active" in text or "Brief" in text):
            return "Cook mode active. Tell me — what are we cooking today? Do you need today's brief or step-by-step recipe instructions?"
        if "Household mode" in text:
            return "Household mode active. What would you like to do — meal plan, grocery list, or place an order?"
        if "Bhej diya (simulated)" in text:
            return text.replace("Bhej diya (simulated)", "Sent via WhatsApp (simulated)").replace("Total Rs.", "Total ₹").replace("Poori list:", "Full list:")
        if "Done —" in text:
            t = text.replace("Done —", "Done —")
            t = t.replace("ki jagah", "instead of")
            t = t.replace("Kuch aur?", "Anything else?")
            return t
        if "Note kar liya —" in text:
            return text.replace("Note kar liya —", "Noted —").replace("Aur kuch?", "Anything else?")
        if "Aaram karo." in text:
            return text.replace("Aaram karo. Aaj sirf:", "Take rest today. Today only:").replace("Bas.", "That is all.")
        if "Sabse pehle" in text:
            t = text.replace("Aaj", "Today is").replace("Sabse pehle", "First start with").replace("shuru karo. Phir", ". Then")
            return t
        return text

    return text
