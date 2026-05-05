# KitchenOS v2.0: The Autonomous Pantry

KitchenOS is a multi-agent system that manages your kitchen — from dietary profiles and recipe search to grocery procurement and savings calculation. Built on Google ADK, it uses five specialized agents to handle the full pipeline from "what's for dinner?" to "items ordered."

## Quick Start

```bash
# 1. Clone & enter
git clone <repo-url> && cd mychef

# 2. Set up your .env (see "Configuration" below)

# 3. Run everything
docker compose up --build

# 4. Open
#    ADK Dev UI  →  http://localhost:8000
#    KitchenOS UI →  http://localhost:5050
```

---

## Prerequisites

| Tool | Why | Install |
|---|---|---|
| **Docker & Docker Compose** | Runs all services (Postgres, ADK, Web UI) | [docs.docker.com](https://docs.docker.com/get-docker/) |
| **Ollama** | Runs the LLM locally on your machine | [ollama.com](https://ollama.com) |
| **Node.js 20+** | Required by MCP servers (Spoonacular, Postgres) spawned via `npx` | [nodejs.org](https://nodejs.org) |

### Pull the LLM Model

KitchenOS uses `gpt-oss:120b-cloud` via Ollama. Pull it before starting:

```bash
ollama pull gpt-oss:120b-cloud
```

Verify it's available:

```bash
ollama list | grep gpt-oss
# Should show: gpt-oss:120b-cloud
```

---

## Configuration

Create a `.env` file in the project root:

```env
# ─── Spoonacular API Key (REQUIRED) ───
# Get a free key at: https://spoonacular.com/food-api/console
spoonacular_api_key=YOUR_SPOONACULAR_API_KEY

# ─── Swiggy Access Token (OPTIONAL — for procurement features) ───
# See "Connecting Swiggy" section below
SWIGGY_ACCESS_TOKEN=
```

### Getting a Spoonacular API Key

1. Go to [spoonacular.com/food-api/console](https://spoonacular.com/food-api/console)
2. Sign up for a free account
3. Copy your API key from the dashboard
4. Paste it into `.env` as `spoonacular_api_key=<your-key>`

### Connecting Swiggy (Optional)

Swiggy MCP requires an OAuth access token. KitchenOS includes a helper script:

```bash
python auth_swiggy.py
```

This will:
1. Print an authorization URL → open it in your browser
2. Log into your Swiggy account
3. You'll be redirected to `http://localhost/callback?code=...` (the page won't load — that's expected)
4. Copy the **full URL** from your browser's address bar into a file called `swiggy_url.txt` in the project root
5. Press Enter in the terminal
6. The script exchanges the code for a token and prints your `SWIGGY_ACCESS_TOKEN`
7. Paste the token into your `.env` file

> **Note:** Swiggy tokens expire after ~5 days. Re-run `auth_swiggy.py` when needed. Without a valid token, the Shopper agent will skip Swiggy features but all other agents work normally.

---

## Running

### With Docker (Recommended)

```bash
docker compose up --build
```

This starts three services:

| Service | Port | Description |
|---|---|---|
| `mychef-postgres` | 5432 | PostgreSQL with pantry, family, and dietary data |
| `mychef-app` | 8000 | Google ADK backend (agent orchestration engine) |
| `mychef-web` | 5050 | KitchenOS Web UI (landing page + chat) |

### Without Docker (Local Dev)

```bash
# Terminal 1: Start Postgres (or use an existing instance)
# Make sure POSTGRES_CONNECTION_STRING in .env points to your DB

# Terminal 2: Start ADK
pip install -r requirements.txt
adk web agents/

# Terminal 3: Start Web UI
cd web
pip install -r requirements.txt
python app.py
```

---

## Verifying Connections

KitchenOS ships with test suites to verify every integration layer.

### 1. Verify Agent Structure

Checks that all 5 agents (Chef, Diet, Recipe, Shopper, Budget) are correctly wired:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_agent.py -v
```

Expected: **23 passed** ✅

### 2. Verify Ollama / LLM

Checks that Ollama is running and the model responds:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_ollama.py -v
```

Expected output:
- `test_ollama_is_running` — Ollama API reachable at `localhost:11434`
- `test_ollama_has_target_model` — `gpt-oss:120b-cloud` is pulled
- `test_litellm_completion_to_ollama` — LiteLLM routes to Ollama successfully
- `test_agent_model_uses_openai_prefix` — Agent config is correct

### 3. Verify Spoonacular MCP

Checks that the Spoonacular MCP server launches and exposes recipe tools:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_mcps.py::test_spoonacular_mcp_starts_and_lists_tools -v
```

Expected: prints available tools like `search_recipes`, `get_recipe_information`, etc. If your API key is invalid, the server may still start but tool calls will fail.

### 4. Verify Postgres MCP

Checks that the Postgres MCP server launches and can query the database:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_mcps.py::test_postgres_mcp_starts_and_lists_tools -v
```

Expected: prints tools like `query`. Requires Postgres to be running on `localhost:5432`.

### 5. Verify Swiggy MCP

Checks that the Swiggy MCP endpoint is reachable with your token:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_mcps.py::test_swiggy_mcp_starts_and_lists_tools -v
```

Expected: prints available Swiggy tools. Will **skip** (not fail) if the token is expired or missing.

### Run All Tests

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -v
```

---

## Architecture

>  **[Full Pipeline Architecture →](pipeline_architecture.md)** — User types, user stories, API endpoints, UML class diagrams, sequence diagrams, routing logic, infrastructure topology, safety guardrails, and testing matrix.

### The Agents

| Agent | Role | Tools | Data Source |
|---|---|---|---|
| **Chef** | Orchestrator — delegates and compiles results | None (pure delegation) | — |
| **Diet** | Fetches dietary profiles, allergies, pantry | Postgres MCP, Spoonacular MCP | `family_members`, `dietary_profiles`, `pantry` tables |
| **Recipe** | Finds recipes and calculates missing ingredients | Spoonacular MCP, Postgres MCP | Spoonacular API |
| **Shopper** | Prices and orders items on Swiggy | Postgres MCP, Swiggy MCP (×3) | Swiggy Instamart / Food / Dineout |
| **Budget** | Calculates savings (cook vs. order) | None (calculation only) | — |

### Communication Protocol

- Sub-agents **never** talk to the user directly
- If a sub-agent needs clarification, it returns the question to the **Chef**
- The **Chef** is the sole spokesperson — it asks you and relays answers

### The Family Dinner Protocol

```
User: "Dinner for the family tonight"
  → Chef delegates to Diet (fetch profiles & allergies from DB)
  → Chef delegates to Recipe (find Spoonacular recipes + gap analysis)
  → Chef delegates to Shopper (price missing items on Swiggy)
  → Chef delegates to Budget (calculate savings)
  → Chef presents: "Missing 2 items. Savings: ₹450. Order?"
  → User: "Yes"
  → Chef delegates to Shopper (execute order + update DB ledger)
```

### Database Schema

Seeded automatically by `init.sql`:

- **`family_members`** — name, relationship (self, spouse, child, etc.)
- **`dietary_profiles`** — per-member traits (allergy, diet, dislike, favorite)
- **`pantry`** — item_name, quantity, unit, purchase_date, expiry_date

### MCP Integrations

| MCP Server | Transport | Purpose |
|---|---|---|
| **Spoonacular** | stdio (`npx spoonacular-mcp`) | Recipe search, nutrition data |
| **Postgres** | stdio (`npx mcp-postgres`) | Database queries and writes |
| **Swiggy Instamart** | HTTP (`https://mcp.swiggy.com/im`) | Grocery search, cart, pricing |
| **Swiggy Food** | HTTP (`https://mcp.swiggy.com/food`) | Restaurant search |
| **Swiggy Dineout** | HTTP (`https://mcp.swiggy.com/dineout`) | Dine-out options |

---

## Project Structure

```
mychef/
├── agents/head_chef/
│   ├── agent.py           # Agent definitions and MCP toolset wiring
│   └── prompts.py         # All agent instructions
├── web/
│   ├── app.py             # Flask server (port 5050)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── templates/
│       ├── index.html     # Landing page with live DB dashboard
│       └── chat.html      # Chat interface
├── tests/
│   ├── test_agent.py      # Agent structure tests (23 assertions)
│   ├── test_mcps.py       # MCP connection tests
│   └── test_ollama.py     # LLM integration tests
├── auth_swiggy.py         # Swiggy OAuth helper
├── init.sql               # Database seed (tables + sample data)
├── docker-compose.yml     # 3-service stack (Postgres, ADK, Web)
├── Dockerfile             # ADK container
├── requirements.txt       # Python dependencies
└── .env                   # API keys (not committed)
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Failed to create MCP session` for Spoonacular | Check that `spoonacular_api_key` is set in `.env` and Node.js/npx is installed |
| `Failed to create MCP session` for Swiggy | Token expired — re-run `python auth_swiggy.py` |
| Ollama model not found | Run `ollama pull gpt-oss:120b-cloud` |
| Postgres connection refused | Ensure `docker compose up` has started the postgres container, or run Postgres locally on port 5432 |
| Web UI shows "ADK offline" | The ADK backend on port 8000 hasn't finished starting yet — wait 10-15 seconds |
| `npm error process terminated` in logs | Non-fatal — the ADK dev-ui npm process exits but the backend still works |

---

## Safety

The Shopper agent has a hard-coded safety rule: **it will NEVER place an actual Swiggy order or checkout**. It can search, price, and add items to the cart for bill estimation, but final order placement is blocked.
