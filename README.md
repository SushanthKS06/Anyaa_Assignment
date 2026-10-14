# Rasoi (रसोई / சமையலறை) — Household Meal-Planning & Kitchen Operating System

> **A dual-persona, neuro-symbolic voice agent built for real Indian household kitchens:** collaborative meal planning with multi-generational families, real-time grocery orchestration, and interactive, hands-free cooking execution with the domestic cook.


---

## 1. Executive Summary & Engineering Philosophy

Most AI meal planners fail in real Indian households because they treat kitchen operations as a naive text generation problem. They hallucinate quantities, quietly forget Jain restrictions on Day 4, neglect the toddler’s portion, or invent impossible cooking times.

**Rasoi is engineered with a strict neuro-symbolic separation of concerns:**
* **Deterministic Python Core Decides:** Safety invariants (allergens, Jain/Sattvic rules, diabetic carb limits, fasting calendars), nutritional variety, portion scaling, grocery math (metric conversions & pack rounding), and financial transaction gates are 100% deterministic code covered by **64 automated tests**.
* **LLMs and Voice Only Verbalize:** The LLM does what it does best — conversational empathy, colloquial phrasing, and constraint extraction with Pydantic validation & repair.
* **One Shared Brain, Two Distinct Registers:**
  1. **Household Persona (`/home`):** Warm, collaborative, empathetic, budget-conscious, and patient.
  2. **Cook Persona (`/cook`):** Direct, operational, respectful, exact ingredient quantities repeated back, step-by-step interactive cooking cards, and hands-free kitchen tools.
* **Zero-Key Deterministic Mock Mode:** The system runs out-of-the-box offline with zero API keys. When live keys are supplied (`GROQ_API_KEY`, `GEMINI_API_KEY`, `SARVAM_API_KEY`), it seamlessly transitions to live LLM generation and Indic voice streaming.

---

## 2. System Architecture

graph TD
    User([User Voice / Text]) --> VoiceLayer["Voice Gateway: Web Speech / Sarvam AI / VAD Barge-in"]
    VoiceLayer --> Router["Intent & Language Router: Auto-detect en-IN / ta-IN / hi-IN"]

    subgraph SharedBrain["Shared Brain: Orchestrator State Machine & SQLite WAL"]
        Router --> ModeCheck{"Active Mode?"}
        ModeCheck -->|Household| HouseholdPersona["Household Persona: Warm & Collaborative"]
        ModeCheck -->|Cook| CookPersona["Cook Persona: Direct & Operational"]

        HouseholdPersona <--> StateStore[("Household Constraints & Plan State")]
        CookPersona <--> StateStore
    end

    subgraph DeterministicEngine["Deterministic Engine: Python Core"]
        StateStore --> Planner["Constraint Solver & Meal Planner"]
        Planner --> Adaptations["Adaptation Splitter: Toddler / Jain / Non-Veg / Allergies"]
        Adaptations --> GroceryEngine["Grocery Normalizer & Pantry Deductor"]
        GroceryEngine --> InstamartMock["Simulated Instamart Cart & Stock-Out Recovery"]
        GroceryEngine --> WhatsAppMock["Simulated WhatsApp Cook Handoff"]
        CookPersona --> KitchenEngine["Kitchen Disruptions: Guests / 20-Minute Meals / Swaps"]
    end

    subgraph InteractiveUI["Interactive UI Cockpit: FastAPI + WebSocket"]
        StateStore --> WebCockpit["Live Cockpit: Real-Time Plan, Cart & Cook Companion Cards"]
        Planner --> WebCockpit
        GroceryEngine --> WebCockpit
        KitchenEngine --> WebCockpit
    end


---

## 3. Real-World Kitchen Scenarios Handled

Real Indian households are beautifully messy. Rasoi is purpose-built to solve these exact edge cases:

| Real-Life Scenario | The Kitchen Reality | How Rasoi Solves It Deterministically |
|---|---|---|
| **Multi-Diet Household** | Dadi is strictly Jain, father and kids eat non-veg (chicken/egg), mother is vegetarian. | The planner balances omnivore preferences by scheduling non-veg dishes for lunch/dinner while generating **first-class adaptation splits** (`separate vegetarian/paneer portion for Dadi/Mother`). |
| **Toddler in the Family** | 2-year-old child cannot eat spicy or hard foods. | Automatically generates mild, zero-chilli, soft-mashed toddler portions as first-class plan metadata on every meal chip. |
| **Allergy Invariant** | Family member allergic to peanuts or carrots. | **Zero Silent Relaxation Policy:** Any dish containing the allergen is rejected at the engine level. Never quietly bypassed. |
| **Vrat & Fasting Days** | Navratri, Ekadashi, or Shravan Mondays. | Fasting rules strictly enforce grain and onion-garlic exclusion (swaps to Sabudana Khichdi, Kuttu Paratha), never allowing potato or onion leaks. |
| **Pantry & Budget Limits** | Household has ₹5,000 budget and existing staples in pantry. | Normalizes pantry stock (e.g. 500g suji in stock), subtracts from grocery requirements, rounds up to retail pack sizes, and gates orders behind explicit household confirmation. |
| **Mid-Day Cooking Disruptions** | "2 guests arrived", "we ran out of tomatoes", "cook is on leave today", "need dinner in 20 mins". | Cook mode triggers real-time portion scaling, deterministic ingredient substitution, 20-minute rush meal filtering, or one-pot batch suggestions. |

---

## 4. Key Highlights & Features

### 4.1 Native Tri-Lingual Parity (Tamil, English, Hindi)
Full end-to-end parity across three languages with dynamic script detection:
* **Tamil (தமிழ்):** Complete native Tamil script output, Tamil ingredient translations (`வெங்காயம்`, `தக்காளி`, `மஞ்சள் தூள்`), and step-by-step cooking steps (`படி 1`, `படி 2`).
* **English:** Clear, natural conversational English with accurate metric kitchen units.
* **Hindi (हिन्दी / Hinglish):** Warm Hindi/Hinglish with cultural idioms (`"Dadi ke liye alag se banayenge"`).

### 4.2 Interactive Cook Companion Cockpit
In Cook Mode, recipe instructions are transformed into a culinary cockpit card:
* **Mise en Place Checklist:** Ingredients displayed in a 3-column responsive grid with interactive checkboxes. Tapping an item marks it gathered with a green checkmark and strikethrough. Exact quantities are highlighted in emerald badges (`8 pieces`, `160 g`, `2 tsp`).
* **Sequenced Cooking Cards:** Step-by-step progress cards (`Step 1`, `படி 1`, `कदम 1`) with click-to-complete toggles.
* **Live Kitchen Timers:** One-click `⏱️ 5m Timer` and `⏱️ 15m Timer` with active countdown badges.
* **Text-to-Speech:** `🔊 Read Steps` button allows hands-free listening while standing at the stove.

---

## 5. REAL vs. SIMULATED (Radical Engineering Honesty)

In accordance with the assignment guidelines, here is an exact, transparent disclosure of system boundaries:

| Component | Status | Details |
|---|---|---|
| **Constraint Solver & Planner** | **REAL** | Deterministic Python scoring, allergen pruning, diversity penalty, non-veg prioritization, toddler adaptations. |
| **Grocery Math & Pack Rounding** | **REAL** | Unit normalization (`g`, `kg`, `ml`, `l`, `pieces`, `packs`), pantry inventory deductions, minimum pack calculations. |
| **State Machine & Persistence** | **REAL** | SQLite WAL database (`data/app.db`) persists households, members, plans, cook logs, and cart history. |
| **Tri-lingual Extraction & Routing** | **REAL** | Multi-lingual script detection, regex/keyword scoring, and Pydantic-validated LLM extraction with repair retries. |
| **Web Cockpit UI** | **REAL** | Real-time WebSocket cockpit (`web/index.html`) featuring live state, interactive meal planner, and recipe cards. |
| **Voice & Speech Gateway** | **REAL** | Browser WebSpeech API for live voice recognition & synthesis; Sarvam AI REST API client fully wired for production keys. |
| **VAD Barge-in** | **REAL** | Client-side voice activity detection interruption with server-side speech truncation. |
| **Instamart Order Placement** | **SIMULATED** | High-fidelity mock simulating catalog search, stock-out detection, replacement suggestions, and checkout IDs. |
| **WhatsApp Cook Handoff** | **SIMULATED** | Generates real formatted WhatsApp dispatch messages with copy-to-clipboard and message link simulation. |
| **Recipe Knowledge Base** | **REAL** | 50 authentic Indian home-cooking recipes with scaled ingredients, prep/cook times, and dietary tags. |

---

## 6. Quickstart & Verification (3 Minutes)

### Prerequisites
* Windows PowerShell (or macOS / Linux terminal)
* Python 3.11 or higher

### Step 1: Install Dependencies
```powershell
pip install -r requirements.txt
```
*(Or manually: `pip install fastapi uvicorn "pydantic>=2.7" httpx tenacity pytest rich python-dotenv pyyaml google-genai groq`)*

### Step 2: Environment Configuration (Optional)
```powershell
Copy-Item .env.example .env
```
> **Note:** The system works 100% offline in deterministic mock mode without API keys! If you have keys, add `GROQ_API_KEY`, `GEMINI_API_KEY`, or `SARVAM_API_KEY` to `.env` to activate live models.

### Step 3: Run Smoke Test & Unit Tests
```powershell
# Run self-check smoke test
python scripts/smoke_test.py

# Run all 64 unit & integration tests
pytest evals -q
```

### Step 4: Run Scenario Evaluations (14 Benchmarks)
```powershell
python evals/run_evals.py
```
*Output: Rich formatted benchmark table with **0 failing checks** across all 14 scenarios.*

### Step 5: Launch the Interactive Web Cockpit
```powershell
uvicorn app.main:app --reload
```
Open your browser to: **`http://127.0.0.1:8000/`**
* Test voice or text conversation in English, Tamil, or Hindi.
* Toggle between **Household Mode** (`mode: household`) and **Cook Mode** (`mode: cook`).
* Ask for recipe steps: *"Like to know? Step by step preparation for egg Curry."*
* Interact with the checkable ingredient list, timers, and meal plan chips.

---

## 7. Interactive Tour & CLI Demos

| Script | Purpose | What It Proves |
|---|---|---|
| `python scripts/scripted_convo.py` | 10-turn Household Flow | Multi-turn onboarding → constraint extraction → meal plan generation → swap → out-of-stock recovery → confirm-gated order. |
| `python scripts/scripted_cookday.py` | Cook Day Simulation | Morning brief → guest scaling disruption → missing ingredient swap → cook log and taste feedback. |
| `python scripts/chat.py` | Interactive CLI Chat | Full terminal-based interactive agent with mode switching (`/home`, `/cook`). |
| `python scripts/show_plan.py` | Deterministic Planner Demo | Generates a 7-day balanced plan for a multi-diet household and prints formatted daily schedules. |
| `python scripts/demo_grocery.py` | Grocery & WhatsApp Demo | Takes a meal plan, subtracts pantry stock, rounds to store packs, and formats the WhatsApp cook dispatch. |

---

## 8. Evaluation Suite & Quality Gates

The test suite in `evals/` ensures that regressions cannot enter the system:
1. **64 Deterministic Unit & Integration Tests (`pytest evals/`):**
   - Diet constraint satisfaction (Jain, vegan, vegetarian, non-veg).
   - Allergen hard exclusion (peanuts, carrots, gluten, dairy).
   - Servings math and grocery unit conversions.
   - Confirm-gated financial safety (cannot order without explicit user confirmation).
   - Cook mode conversational boundaries (cook mode never repeats household intake questions).
   - Trilingual recipe steps formatting and language detection accuracy.
2. **14 Multi-Turn Benchmark Scenarios (`evals/run_evals.py`):**
   - Tests complex scenarios including: `joint_jain_nonveg`, `diabetic_elder`, `toddler_soft_food`, `navratri_fasting`, `surprise_guests`, `tight_budget`, `cook_on_leave`, and `wrong_item_delivered`.
   - Primary evaluation uses deterministic assert checkers (`evals/checks.py`); secondary evaluation uses heuristic rubrics (`evals/judge.py`).

---

## 9. Codebase Layout

```
Anyaa_Assignment/
├── app/
│   ├── agent/
│   │   ├── orchestrator.py    # Main state machine, turn handlers, tri-lingual mirroring
│   │   ├── router.py          # Language detection (ta/en/hi) & mode switching (/home vs /cook)
│   │   ├── personas.py        # System prompts and conversational registers for Household vs Cook
│   │   ├── extract.py         # Pydantic constraint extractor with validation & retry
│   │   ├── llm.py             # Resilient LLM wrapper (Gemini 2.5 Flash -> Groq -> Mock fallback)
│   │   └── tools.py           # Tool dispatch registry (plan, swap, grocery, cook disruptions)
│   ├── engine/
│   │   ├── models.py          # Core Pydantic domain models (Household, Member, Recipe, MealPlan)
│   │   ├── planner.py         # Deterministic scoring, nutrient variety, non-veg prioritization
│   │   ├── constraints.py     # Hard constraint checks (diets, allergens, fasting days)
│   │   ├── adaptations.py     # Sub-recipe splitter (toddler portions, Jain portions, veg swaps)
│   │   ├── groceries.py       # Unit normalization, pantry subtraction, retail pack rounding
│   │   ├── kitchen.py         # Cook disruptions (guest scaling, substitutions, rush meals)
│   │   ├── recipe_steps.py    # Scaled ingredient quantities & tri-lingual cooking steps
│   │   ├── instamart_mock.py  # Simulated Instamart cart & stock-out handler
│   │   └── whatsapp_mock.py   # Formatted cook dispatch message generator
│   ├── voice/
│   │   ├── session.py         # Voice session management, event streaming, barge-in handling
│   │   ├── stt.py             # Speech-to-Text gateway (Sarvam AI / browser WebSpeech fallback)
│   │   └── tts.py             # Text-to-Speech gateway & audio chunk synthesis
│   ├── store/
│   │   └── db.py              # SQLite WAL persistence for households, plans, cook logs, carts
│   ├── config.py              # Environment configuration and feature flags
│   └── main.py                # FastAPI HTTP & WebSocket server
├── data/
│   ├── recipes.json           # 50 authentic Indian recipes with macro data & ingredients
│   ├── instamart_catalog.json # Simulated store catalog with pack sizes & prices
│   └── festivals.json         # Indian cultural & fasting calendar definitions
├── evals/
│   ├── scenarios/             # 14 YAML end-to-end benchmark scenarios
│   ├── checks.py              # Deterministic evaluation checkers
│   ├── judge.py               # Heuristic evaluation rubrics
│   ├── sim_user.py            # Simulated user conversation driver
│   ├── run_evals.py           # Benchmark runner with Rich table reporting
│   └── test_*.py              # 64 pytest unit and integration test suites
├── scripts/
│   ├── smoke_test.py          # System health check script
│   ├── scripted_convo.py      # End-to-end household planning demonstration
│   ├── scripted_cookday.py    # End-to-end cook execution demonstration
│   ├── show_plan.py           # Plan generator CLI preview
│   ├── demo_grocery.py        # Grocery calculation CLI preview
│   └── chat.py                # Interactive terminal chat client
├── web/
│   └── index.html             # Realtime cockpit with interactive recipe companion cards
├── WRITEUP.txt                # One-page executive writeup covering decisions & roadmap
├── WRITEUP.md                 # Markdown version of the executive writeup
├── Dockerfile                 # Multi-stage production container
├── docker-compose.yml         # Container orchestration with volume mounts
├── Procfile                   # Cloud PaaS (Render / Railway) web runner
├── .dockerignore              # Clean container build filter
├── requirements.txt           # Python package dependencies
└── README.md                  # This file
```

---

## 10. Deployment Guide

Rasoi is a self-contained FastAPI application serving static assets, WebSockets, and background state. You can deploy it live in under 2 minutes:

### Option A: Free Cloud Deployment (Render.com) — *Recommended for Demos*
1. Push your repository to GitHub.
2. Sign in to [Render.com](https://render.com) and click **New + > Web Service**.
3. Select your repository.
4. Set the following settings:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. *(Optional)* Add environment variables in Render Dashboard: `GROQ_API_KEY`, `GEMINI_API_KEY`, `SARVAM_API_KEY`.
6. Click **Deploy**. Render provides a live `https://*.onrender.com` URL with SSL and WebSocket support out of the box!

### Option B: Railway.app / Fly.io (One-Click Docker)
Because the repository includes a production `Dockerfile` and `Procfile`, Railway and Fly auto-detect the configuration:
```bash
# Fly.io deployment
fly launch
fly deploy
```

### Option C: Docker & Docker Compose
```bash
# Build and run container locally or on any VPS
docker-compose up -d --build

# Inspect running container
docker ps
# Open http://localhost:8000/
```

### Option D: Immediate Mobile Kitchen Test (Cloudflare Tunnel / Ngrok)
To test the voice agent hands-free on your smartphone in an actual kitchen right now:
```powershell
# In terminal 1: start the server
uvicorn app.main:app --reload

# In terminal 2: expose via Cloudflare Tunnel or Ngrok
npx untun@latest tunnel http://localhost:8000
# OR:
ngrok http 8000
```
Open the generated HTTPS URL on your phone's browser, tap **Allow Microphone**, and interact with the cook companion hands-free while cooking!

---

## 11. License & Submission Info

Built for the **Anyaa Internship Assignment: Household Meal-Planning Voice Agent**.
Designed and engineered with care for the complexities of real Indian kitchens.
