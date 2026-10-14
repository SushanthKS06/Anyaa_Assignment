"""Mode router. Deterministic keyword detection (no LLM needed).
Cook mode triggers on cook-voice markers or explicit /cook; everything else
is household mode. Explicit /home switches back."""
from __future__ import annotations

import re

COOK_MARKS = [
    r"\bcook\b", r"rasoi (me|se)", r"\bchef\b", r"bana diya", r"bana di\b",
    r"khaana (ban|taiyaar)", r"tiffin (pack|ready)", r"order (aaya|deliver)",
    r"gas (khatm|kharab)", r"pressure cooker", r"namak (zyada|kam)",
    r"main (cook|maharaj)", r"khana bana", r"bataya tha",
    r"kharab", r"khatm ho", r"\bbrief\b", r"taiyari",
    # Tamil cook voice marks
    r"சமை", r"சமையல்", r"ஸ்டெப்", r"செய்முறை", r"படி", r"குக்கர்", r"சாப்பாடு",
    r"samayal", r"samaik", r"senjachu", r"samachachu", r"step", r"recipe",
]
# guest words never switch modes alone: in cook mode they mean a disruption,
# in household mode they are just extraction context.
HOUSEHOLD_MARKS = [r"plan (bana|kar)", r"grocery", r"instamart", r"budget",
                   r"order (kar|place|karo)", r"whatsapp", r"மளிகை", r"பட்ஜெட்"]


def detect_mode(text: str, current: str = "household") -> tuple[str, bool]:
    t = text.strip().lower()
    if t.startswith("/cook"):
        return "cook", current != "cook"
    if t.startswith("/home"):
        return "household", current != "household"
    cook_hit = any(re.search(p, t) for p in COOK_MARKS)
    home_hit = any(re.search(p, t) for p in HOUSEHOLD_MARKS)
    if cook_hit and not home_hit:
        return "cook", current != "cook"
    if home_hit and not cook_hit:
        # sticky cook mode: only strong planning words pull back to household
        if current == "cook" and not re.search(r"grocery|instamart|order|whatsapp|budget|மளிகை|பட்ஜெட்", t):
            return "cook", False
        return "household", current != "household"
    return current, False


TAMIL_WORDS = set(
    "vanakkam paati patti thatha appa amma kuzhandhai pappa kadalai verkkadalai "
    "pannunga panrathu pannalam pannu irukku irukaanga roobai rooba aayiram naal naatkal "
    "enna samayal thakkali venum venaam vendam koodathu illai thappu seri aam "
    "sollunga innum aduthu aarambi kaalai madhiyam mathiyam iravu saayandhiram "
    "virundhinar viradham viratham nombu veetula veetu seiyala seiyalam thirumba "
    "eppadi yean yen ungal ungalukku enakku nalla romba konjam podunga maathu "
    "badhil vaangu anuppu thaan kellinga".split()
)

HINDI_WORDS = set(
    "namaste dadi papa chhotu bhai bana banao banaiye banau batao rakhu rakho rakh theek "
    "kitna kitne kitni hazaar hazaari rupaye din nashta dopahar raat khatam chhutti "
    "mehman aaj kal nahi haan suno khana pehle kya kaise karo karein hai hain tha "
    "thi the gaya gayi gaye aur saaman samaan badal badlo jagah bhigo pakka bilkul "
    "apne apni apna tumhare tumhara tumhari hum hume mujhe mera meri mere kripya "
    "chahiye khao khate thoda zyada sabse achha achhi lo do ho humare".split()
)

ENGLISH_STRUCT = set(
    "the is are am was were be been being have has had do does did will would shall "
    "should can could may might must hello hi please make create why what when where "
    "how who which whose whom from with about into between through during before after "
    "because then so than too very just now tell give talk speak answer want see if "
    "to for by like know step preparation recipe ingredients details cook cooking curry "
    "dish food instructions help thanks thank you me my we our us i need want can "
    "show explain give get make process method portion portions meal meals plan items used quantity".split()
)


def detect_language(text: str, current: str = "hi-IN") -> str:
    """Detect language: 'ta-IN' (Tamil), 'en-IN' (English), or 'hi-IN' (Hindi/Hinglish)."""
    t = text.strip()
    if not t:
        return current
    low = t.lower()

    # Check if only one language is explicitly asked for
    langs = [l for l in ["tamil", "english", "hindi"] if l in low]
    if len(langs) == 1:
        target = langs[0]
        if target == "tamil" and re.search(r"(speak|talk|answer|bolo|sol|pesu|in\s+tamil)", low):
            return "ta-IN"
        if target == "english" and re.search(r"(speak|talk|answer|bolo|sol|pesu|in\s+english)", low):
            return "en-IN"
        if target == "hindi" and re.search(r"(speak|talk|answer|bolo|sol|pesu|in\s+hindi)", low):
            return "hi-IN"

    # Unicode script check
    if re.search(r"[\u0B80-\u0BFF]", t):
        return "ta-IN"
    if re.search(r"[\u0900-\u097F]", t):
        return "hi-IN"

    # Token-level voting for Latin transliterated inputs
    words = re.findall(r"[a-zA-Z]+", low)
    tc = sum(1 for w in words if w in TAMIL_WORDS)
    hc = sum(1 for w in words if w in HINDI_WORDS)
    ec = sum(1 for w in words if w in ENGLISH_STRUCT)

    if tc > 0 and tc >= hc and tc >= ec:
        return "ta-IN"
    if hc > 0 and hc >= tc and hc >= ec:
        return "hi-IN"
    if ec > 0 and ec > hc and ec > tc:
        return "en-IN"
    if tc > hc:
        return "ta-IN"
    if hc > tc:
        return "hi-IN"
    if ec > 0:
        return "en-IN"
    return current
