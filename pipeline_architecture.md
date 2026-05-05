# KitchenOS Pipeline Architecture

> Complete software lifecycle document — from user types and stories through API surface, data model, agent hierarchy, and runtime execution.

---

## 1. User Types & Permissions

| User Type | Role | Capabilities |
|---|---|---|
| **Owner** | Head of Household | Full DB access, financial thresholds, guest approval, order execution |
| **Member** | Family Resident | Update personal "Card" (preferences/allergies), trigger meal plans, add to cart |
| **Guest** | Transient Profile | Read-only preference injection for a single session (e.g., dinner party) |

### Permission Matrix

| Action | Owner | Member | Guest |
|---|---|---|---|
| Trigger meal plan | ✅ | ✅ | ❌ |
| Update dietary profile | ✅ | ✅ (own only) | ❌ |
| Modify pantry | ✅ | ✅ | ❌ |
| Approve Swiggy order | ✅ | ❌ | ❌ |
| View pantry / profiles | ✅ | ✅ | ✅ (session only) |

---

## 2. User Stories

### US-01: The Family Dinner
> "As an Owner, I want to say 'Dinner for the family tonight' and have the system plan a meal that respects everyone's dietary constraints, identify missing ingredients, price them on Swiggy, and tell me my savings — so I only need to say 'Yes' to order."

**Acceptance Criteria:**
- Dietary profiles fetched from Postgres (not assumed)
- Recipe sourced from Spoonacular (not hardcoded)
- Missing items priced on Swiggy Instamart
- Savings calculated (home cooking vs. delivery)
- User must explicitly approve before any order executes

### US-02: Pantry Audit
> "As a Member, I want to ask 'What's expiring soon?' and get a sorted list of pantry items by expiry date."

**Acceptance Criteria:**
- Data comes from `pantry` table only
- Sorted by `expiry_date ASC`
- Items expiring within 3 days flagged

### US-03: Price Check
> "As an Owner, I want to ask 'What's the price of milk?' and get the current Swiggy Instamart price without placing any order."

**Acceptance Criteria:**
- Shopper agent searches Swiggy Instamart
- Returns price and availability
- No cart modification or order placement

### US-04: Profile Management
> "As a Member, I want to tell the system 'Priya is allergic to peanuts' and have it update the database."

**Acceptance Criteria:**
- Shopper agent inserts into `dietary_profiles`
- Confirmation via SELECT back

### US-05: Zero-Waste Cooking
> "As a Member, I want the system to suggest recipes that prioritize expiring ingredients so that I minimize food waste."

**Acceptance Criteria:**
- Diet agent fetches expiring items from pantry
- Recipe agent filters Spoonacular results to maximize use of those items

---

## 3. API Surface

### 3.1 ADK Backend (Port 8000)

These are the Google ADK endpoints the Web UI proxies through:

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/apps/head_chef/users/{user_id}/sessions` | Create a new chat session |
| `POST` | `/run_sse` | Send a message and stream the agent response via SSE |
| `GET` | `/debug/trace/session/{session_id}` | Debug trace for a session |

**SSE Payload (POST `/run_sse`):**
```json
{
  "app_name": "head_chef",
  "user_id": "user",
  "session_id": "<uuid>",
  "new_message": {
    "role": "user",
    "parts": [{ "text": "Dinner for the family tonight" }]
  },
  "streaming": false
}
```

**SSE Response Stream:**
Each line is `data: <json>`. The relevant fields:
```json
{
  "author": "Chef",
  "content": {
    "parts": [{ "text": "..." }]
  }
}
```

### 3.2 Web UI Backend (Port 5050)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Landing page |
| `GET` | `/chat` | Chat interface |
| `POST` | `/api/session` | Proxy: creates ADK session, returns `{ session_id }` |
| `POST` | `/api/chat` | Proxy: forwards message to ADK `/run_sse`, streams response |
| `GET` | `/api/pantry` | Direct DB: returns pantry items as JSON |
| `GET` | `/api/family` | Direct DB: returns family members + dietary traits |
| `GET` | `/api/schema` | Direct DB: returns table/column definitions from `information_schema` |

### 3.3 MCP Endpoints (Internal)

| MCP Server | Transport | Endpoint / Command |
|---|---|---|
| Spoonacular | stdio | `npx -y spoonacular-mcp` |
| Postgres | stdio | `npx -y mcp-postgres` |
| Swiggy Instamart | Streamable HTTP | `https://mcp.swiggy.com/im` |
| Swiggy Food | Streamable HTTP | `https://mcp.swiggy.com/food` |
| Swiggy Dineout | Streamable HTTP | `https://mcp.swiggy.com/dineout` |

---

## 4. Data Model

### Entity-Relationship Diagram

```mermaid
erDiagram
    FAMILY_MEMBERS {
        int id PK
        varchar name
        varchar relationship
    }
    DIETARY_PROFILES {
        int id PK
        int member_id FK
        varchar trait_type
        varchar value
    }
    PANTRY {
        int id PK
        varchar item_name
        float quantity
        varchar unit
        date purchase_date
        date expiry_date
    }

    FAMILY_MEMBERS ||--o{ DIETARY_PROFILES : "has traits"
```

### Table Details

**`family_members`**
| Column | Type | Constraint |
|---|---|---|
| `id` | `SERIAL` | PRIMARY KEY |
| `name` | `VARCHAR(100)` | NOT NULL |
| `relationship` | `VARCHAR(50)` | NOT NULL — `self`, `spouse`, `child`, `parent` |

**`dietary_profiles`**
| Column | Type | Constraint |
|---|---|---|
| `id` | `SERIAL` | PRIMARY KEY |
| `member_id` | `INT` | FK → `family_members(id)` ON DELETE CASCADE |
| `trait_type` | `VARCHAR(20)` | CHECK: `allergy`, `diet`, `dislike`, `favorite` |
| `value` | `VARCHAR(100)` | NOT NULL |

**`pantry`**
| Column | Type | Constraint |
|---|---|---|
| `id` | `SERIAL` | PRIMARY KEY |
| `item_name` | `VARCHAR(100)` | NOT NULL |
| `quantity` | `FLOAT` | DEFAULT 1 |
| `unit` | `VARCHAR(30)` | DEFAULT `'unit'` |
| `purchase_date` | `DATE` | DEFAULT `CURRENT_DATE` |
| `expiry_date` | `DATE` | NULL = non-perishable |

### Seed Data

```sql
-- Family
INSERT INTO family_members (name, relationship) VALUES
    ('User', 'self'), ('Priya', 'spouse');

-- Dietary Profiles
INSERT INTO dietary_profiles (member_id, trait_type, value) VALUES
    (2, 'diet', 'vegetarian'), (2, 'allergy', 'peanuts');

-- Pantry
INSERT INTO pantry (item_name, quantity, unit, purchase_date, expiry_date) VALUES
    ('chicken breast', 2, 'pieces', CURRENT_DATE - 1, CURRENT_DATE + 2),
    ('garlic', 5, 'cloves', CURRENT_DATE - 7, CURRENT_DATE + 21),
    ('heavy cream', 1, 'carton', CURRENT_DATE - 3, CURRENT_DATE + 4),
    ('rice', 2, 'kg', CURRENT_DATE - 30, CURRENT_DATE + 335),
    ('onion', 4, 'pieces', CURRENT_DATE - 5, CURRENT_DATE + 9);
```

---

## 5. Agent Hierarchy (UML Class Diagram)

```mermaid
classDiagram
    class Chef {
        +name: "Chef"
        +role: ORCHESTRATOR
        +tools: None
        +sub_agents: [Diet, Recipe, Shopper, Budget]
        +delegateTask(agent, instruction)
        +compileResults()
        +askUser(question)
    }

    class Diet {
        +name: "Diet"
        +role: READ-ONLY
        +tools: [Postgres MCP, Spoonacular MCP]
        +fetchProfiles() UserCards
        +auditPantry() PantryItems
        +getNutritionalTargets() Targets
    }

    class Recipe {
        +name: "Recipe"
        +role: RECIPE SEARCH
        +tools: [Spoonacular MCP, Postgres MCP]
        +searchRecipes(constraints) RecipeList
        +gapAnalysis(recipe, pantry) GapList
    }

    class Shopper {
        +name: "Shopper"
        +role: WRITE + PROCUREMENT
        +tools: [Postgres MCP, Swiggy IM, Swiggy Food, Swiggy Dineout]
        +priceItems(gapList) PricedItems
        +executeOrder(items) OrderConfirmation
        +updatePantryLedger(items)
    }

    class Budget {
        +name: "Budget"
        +role: CALCULATION ONLY
        +tools: None
        +calculateArbitrage(pricedItems) SavingsReport
    }

    Chef --> Diet : delegates
    Chef --> Recipe : delegates
    Chef --> Shopper : delegates
    Chef --> Budget : delegates
```

### Key Design Constraints

| Constraint | Rationale |
|---|---|
| Chef has **zero tools** | Prevents the orchestrator from bypassing agents and accessing data directly |
| Diet is **read-only** | Separation of concerns — only Shopper can write to the DB |
| Recipe uses **only Spoonacular** for recipes | Recipes must come from a verified culinary API, not hallucinated |
| Sub-agents **never talk to the user** | All clarification flows through Chef to maintain a single conversational thread |
| Budget has **zero tools** | Pure function — takes numbers in, returns savings out |

---

## 6. Communication Protocol

### Question Forwarding Pattern

When a sub-agent lacks information, it does **not** ask the user. Instead:

```mermaid
sequenceDiagram
    participant U as User
    participant C as Chef
    participant D as Diet

    U->>C: "Dinner for 3 tonight"
    C->>D: Fetch profiles for all family members
    D->>D: Query DB — finds only 2 members
    D-->>C: QUESTION: "I found User and Priya. Who is the 3rd person?"
    C->>U: "I found User and Priya in the system. Who is the 3rd person?"
    U->>C: "My friend Rahul, he's allergic to shellfish"
    C->>D: Store Rahul as guest with shellfish allergy
```

### Rules

1. **No agent-to-user communication** — only Chef speaks to the user
2. **No assumptions** — if data is missing, ask (don't default)
3. **Questions propagate upward** — sub-agent → Chef → user → Chef → sub-agent

---

## 7. Runtime Execution: The Family Dinner Protocol

### Full Sequence Diagram

```mermaid
sequenceDiagram
    participant U as User
    participant C as Chef
    participant D as Diet
    participant R as Recipe
    participant S as Shopper
    participant B as Budget
    participant PG as Postgres
    participant SP as Spoonacular API
    participant SW as Swiggy API

    U->>C: "Dinner for the family tonight"

    Note over C: Step 1 — Fetch Profiles
    C->>D: Get dietary profiles and pantry
    D->>PG: SELECT fm.name, dp.trait_type, dp.value FROM family_members fm JOIN dietary_profiles dp ON fm.id = dp.member_id
    PG-->>D: User(self), Priya(vegetarian, peanut allergy)
    D->>PG: SELECT item_name, quantity, unit, expiry_date FROM pantry ORDER BY expiry_date ASC
    PG-->>D: chicken(2d), heavy cream(4d), garlic, rice, onion
    D-->>C: Profiles + Pantry + Targets (prioritize iron/fiber)

    Note over C: Step 2 — Find Recipes
    C->>R: Find recipes. Constraints: vegetarian-friendly, no peanuts. Prioritize expiring: chicken, heavy cream. Targets: high fiber.
    R->>SP: search_recipes(diet=vegetarian, excludeIngredients=peanuts, includeIngredients=chicken,cream)
    SP-->>R: [Chicken Alfredo, Garlic Cream Chicken, ...]
    R->>PG: Check pantry for recipe ingredients
    PG-->>R: Have: chicken, garlic, cream, rice, onion. Missing: lemon, parmesan
    R-->>C: Recipe: "Garlic Cream Chicken". Missing: lemon, parmesan.

    Note over C: Step 3 — Price Missing Items
    C->>S: Price these on Swiggy: lemon, parmesan
    S->>SW: get_addresses()
    SW-->>S: [Address 1: Home]
    S->>SW: search_products("lemon", addressId)
    SW-->>S: Lemon ×4 — ₹30
    S->>SW: search_products("parmesan", addressId)
    SW-->>S: Parmesan 100g — ₹180
    S-->>C: Lemon ₹30, Parmesan ₹180. Total: ₹210.

    Note over C: Step 4 — Calculate Savings
    C->>B: Ingredients cost ₹210. Calculate savings.
    B->>B: Home = ₹210. Delivery = ₹210 × 2.75 + ₹100 = ₹677. Savings = ₹467.
    B-->>C: Total savings: ₹467

    Note over C: Step 5 — Interactive Pause
    C->>U: "Dinner planned: Garlic Cream Chicken. Missing 2 items (₹210). Savings: ₹467. Order?"

    U->>C: "Yes"

    Note over C: Step 6 — Execute
    C->>S: Execute the Swiggy order for lemon and parmesan
    S->>SW: update_cart(lemon, parmesan)
    SW-->>S: Cart total: ₹210. ETA: 15 min.
    S->>PG: INSERT INTO pantry (item_name, quantity, unit, expiry_date) VALUES ('lemon', 4, 'pieces', CURRENT_DATE + 30), ('parmesan', 1, '100g', CURRENT_DATE + 10)
    PG-->>S: 2 rows inserted
    S-->>C: Order added to cart. Pantry updated. Total: ₹210. ETA: 15 min.

    C->>U: "Done. Lemon and parmesan added to your Swiggy cart (₹210, 15 min). Pantry updated. Enjoy the Garlic Cream Chicken!"
```

---

## 8. Agent Routing Logic

When a user message arrives, the Chef routes it based on intent:

```mermaid
flowchart TD
    A[User Message] --> C{Chef: Classify Intent}

    C -->|"buy / order / price / swiggy"| S[Shopper]
    C -->|"recipe / cook / what to make"| R[Recipe]
    C -->|"allergy / diet / profile / pantry audit"| D[Diet]
    C -->|"savings / cost / compare"| B[Budget]
    C -->|"dinner / meal plan"| FDP[Full Dinner Protocol]

    FDP --> D2[1. Diet → fetch profiles]
    D2 --> R2[2. Recipe → find recipes + gap]
    R2 --> S2[3. Shopper → price gaps]
    S2 --> B2[4. Budget → savings]
    B2 --> PAUSE[5. Pause → ask user]
    PAUSE -->|"Yes"| EXEC[6. Shopper → execute]

    S --> RETURN[Return to Chef → User]
    R --> RETURN
    D --> RETURN
    B --> RETURN
```

---

## 9. Infrastructure & Deployment

### Docker Compose Topology

```mermaid
graph LR
    subgraph Docker Network
        PG[(Postgres :5432)]
        ADK[ADK Backend :8000]
        WEB[Flask Web UI :5050]
    end

    subgraph Host Machine
        OLLAMA[Ollama LLM :11434]
        BROWSER[Browser]
    end

    subgraph External APIs
        SPOON[Spoonacular API]
        SWIGGY[Swiggy MCP API]
    end

    WEB -->|proxy /api/chat| ADK
    WEB -->|direct SQL| PG
    ADK -->|stdio MCP| PG
    ADK -->|stdio MCP| SPOON
    ADK -->|HTTP MCP| SWIGGY
    ADK -->|LiteLLM| OLLAMA
    BROWSER -->|:5050| WEB
    BROWSER -->|:8000| ADK
```

### Container Specifications

| Container | Image | Port | Depends On |
|---|---|---|---|
| `mychef-postgres` | `postgres:15-alpine` | 5432 | — |
| `mychef-app` | Custom (Python 3.11 + Node 20) | 8000 | Postgres (healthy) |
| `mychef-web` | Custom (Python 3.11) | 5050 | ADK + Postgres |

---

## 10. Safety & Guardrails

| Rule | Enforcement | Location |
|---|---|---|
| **No actual Swiggy checkout** | Hard-coded in Shopper instruction: "NEVER place an actual order" | `prompts.py` |
| **Diet is read-only** | Instruction says "Never use INSERT, UPDATE, or DELETE" | `prompts.py` |
| **Chef has no tools** | `tools=[]` in agent definition | `agent.py` |
| **No agent-to-user talk** | All sub-agent instructions say "return question to Chef" | `prompts.py` |
| **No hallucinated recipes** | Recipe agent must use Spoonacular MCP exclusively | `prompts.py` |
| **No default assumptions** | Chef instruction: "Do not assume generic defaults" | `prompts.py` |

---

## 11. Testing Matrix

| Test File | What It Verifies | Count |
|---|---|---|
| `test_agent.py` | Agent hierarchy, names, tools, parent relationships | 23 |
| `test_ollama.py` | Ollama reachability, model availability, LiteLLM routing | 4 |
| `test_mcps.py` | Spoonacular MCP launch, Postgres MCP launch, Swiggy MCP connection | 4 |

### Test Commands

```bash
# All tests
PYTHONPATH=. pytest tests/ -v

# Agent structure only
PYTHONPATH=. pytest tests/test_agent.py -v

# Verify Spoonacular is connected
PYTHONPATH=. pytest tests/test_mcps.py::test_spoonacular_mcp_starts_and_lists_tools -v

# Verify Postgres is connected
PYTHONPATH=. pytest tests/test_mcps.py::test_postgres_mcp_starts_and_lists_tools -v

# Verify Swiggy is connected
PYTHONPATH=. pytest tests/test_mcps.py::test_swiggy_mcp_starts_and_lists_tools -v

# Verify LLM works end-to-end
PYTHONPATH=. pytest tests/test_ollama.py::test_litellm_completion_to_ollama -v
```
