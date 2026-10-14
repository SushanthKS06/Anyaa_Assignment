# Writeup — Rasoi: Engineering Decisions, Trade-Offs & Roadmap

> **A short one-page write-up covering key architectural decisions, deliberate trade-offs, cut scope, evaluation findings, and next steps for the Anyaa Household Meal-Planning Voice Agent.**

---

### 1. Core Paradigm: Neuro-Symbolic Kitchen Engine

Meal planning in an Indian household is deceptively complex. It is not an abstract recipe search; it is an optimization problem across overlapping generational diets (Jain elders, non-veg adults, toddlers needing soft mild food), religious calendars (Navratri/Ekadashi fasting), physical pantry stock, and daily operational friction with the domestic cook.

The foundational design decision of Rasoi is a strict neuro-symbolic separation of concerns:
* **Deterministic Python Core Decides:** Hard health/allergen safety, religious diet invariants, macro-variety balancing, metric ingredient scaling, pantry deductions, pack-size rounding, and financial confirm-gating are 100% written in deterministic Python covered by **64 automated tests**.
* **LLM & Voice Only Talk:** The LLM verbalizes the outputs with cultural empathy and extracts unstructured conversational slots into Pydantic models with single-repair retry loops. If the LLM hallucinates or goes offline, the household never receives an allergen, and the bank account is never billed.

---

### 2. Key Architectural Decisions

1. **One Shared Brain, Dual Conversational Registers:**
   Instead of building two disconnected agents, Rasoi uses one unified state machine over SQLite WAL with two situational personas:
   * **Household Register (`/home`):** Collaborative, empathetic, budget-aware, and warm. Guides the family through weekly planning, portion negotiations, and grocery approval.
   * **Cook Register (`/cook`):** Direct, respectful, operational, and concise. Quantities are repeated back immediately; recipe steps are broken down into structured cooking cards with checkable "Mise en Place" ingredient lists, step progress trackers, and hands-free kitchen timers.
   * *Why it matters:* Because both registers operate on the same underlying state, adaptations (e.g., *"Child: zero chilli mashed portion"*, *"Dadi: separate paneer plate"*) are first-class plan metadata that are never lost during handoff.

2. **Zero Silent Relaxation Policy:**
   In health and religious constraints, quiet compromises are catastrophic. If a household requests a meal plan that conflicts with a strict constraint (e.g., Jain fasting on Ekadashi), the engine never silently slips in onion or potato; it either generates an adaptation split (Kuttu / Sabudana) or explicitly flags an unresolvable `CONFLICT` to the user.

3. **Native Tri-Lingual Parity (Tamil, English, Hindi):**
   Rather than treating regional languages as an afterthought, Rasoi features dynamic script detection and full trilingual parity. Speaking or typing in Tamil script yields native Tamil responses, Tamil ingredient names (`வெங்காயம்`, `தக்காளி`), and cooking steps (`படி 1`, `படி 2`). English and Hindi maintain identical architectural and operational fidelity.

---

### 3. Trade-Offs Made Under Time Constraints

* **Rule-Assisted Intent Routing vs. Multi-Second Agentic Tool Loops:**
  High-latency LLM agent loops destroy conversational voice UX. Rasoi uses token-level intent scoring and regex boundaries for mode switches and common commands, ensuring near-instant (<50ms) turn responses while reserving LLM calls for semantic extraction and natural language tone polishing.
* **Seeded Store Catalog vs. Live Scraping:**
  Rather than binding to brittle, unauthenticated quick-commerce APIs that fail randomly during evaluations, we built a high-fidelity simulated catalog with deterministic stock-outs to rigorously test out-of-stock recovery paths.
* **50-Dish Curated Knowledge Base vs. Unbounded Web Scraping:**
  We chose 50 authentic home-style Indian dishes with verified ingredient gram-weights, prep times, and dietary flags rather than ingesting 10,000 messy web recipes that lack standardized household portions.

---

### 4. What Was Deliberately Left Out (and Why)

* **Live Payment Gateway Integration:**
  Real money transactions were deliberately left behind an explicit confirmation gate with simulated order IDs. In a prototype, executing actual financial charges without 2-factor user authorization is unsafe.
* **Raw SIP / WebRTC Audio Streaming:**
  We prioritized an accessible, dependency-free WebSocket architecture supporting browser WebSpeech and Sarvam AI REST rather than requiring complex FreeSWITCH/Twilio telephony infrastructure to run a local demo.
* **Complex Longitudinal Preference Fine-Tuning:**
  Taste feedback and cook logs are persisted to SQLite, but dynamic weight updates across months were deferred to keep the daily planning loop predictable, deterministic, and fully testable.

---

### 5. What the Evaluations Caught & Shaped

Running 14 end-to-end YAML benchmark scenarios and 64 unit tests surfaced several critical edge cases that fundamentally strengthened the system:
1. **Omnivore Meal Skew:** When omnivore members were present, naive random choice frequently scheduled all-veg weeks. We introduced non-veg scoring priority with automatic vegetarian adaptation splits (paneer/tofu) for veg members.
2. **Fasting Root-Vegetable Leak:** Early iterations allowed potato dishes during vrat days; we tightened religious ingredient exclusion rules to strictly enforce sattvic fasting boundaries.
3. **Budget Phrasing Robustness:** User inputs with currency symbols or colloquial phrasing (`"₹5000 வச்சுக்கோ"`, `"budget 6000"`) failed simple regexes; we built a robust multilingual number and currency parser.
4. **LLM Markdown Squashing:** External LLMs frequently compressed structured recipes into unreadable walls of text; we enforced direct deterministic rendering of verified recipes in the UI cockpit.

---

### 6. Production Roadmap (What I Would Build Next)

1. **WhatsApp Business Cloud API Integration:**
   Replace the simulated clipboard handoff with a live interactive WhatsApp bot that sends the cook their daily morning interactive menu with quick-reply buttons (*"All Ingredients Available"*, *"Need Substitutes"*).
2. **Production Indic Voice Pipeline with Edge VAD:**
   Deploy Sarvam AI's streaming speech-to-text and low-latency TTS models coupled with edge-compiled Silero VAD for seamless, noise-tolerant barge-in in noisy kitchen environments.
3. **Vision-Enabled Pantry Auditing:**
   Allow the household or cook to snap a photo of the refrigerator/spice rack; use a multimodal vision model to automatically inventory staples and deduct them from the weekly Instamart cart.
4. **Cross-Family Collaborative Scheduling:**
   Multi-user household synchronization allowing parents, college kids, and elders to RSVP for specific dinner nights, dynamically recalculating batch portions for the cook each morning.
