import os
import asyncio
import shutil
from dotenv import load_dotenv

from google.adk.agents.llm_agent import Agent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams, StreamableHTTPConnectionParams
from mcp.client.stdio import StdioServerParameters

try:
    from head_chef.prompts import (
        DIET_INSTRUCTION, SHOPPER_INSTRUCTION,
        RECIPE_INSTRUCTION, CHEF_INSTRUCTION, BUDGET_INSTRUCTION
    )
except ModuleNotFoundError:
    from agents.head_chef.prompts import (
        DIET_INSTRUCTION, SHOPPER_INSTRUCTION,
        RECIPE_INSTRUCTION, CHEF_INSTRUCTION, BUDGET_INSTRUCTION
    )

load_dotenv()

# Load keys from environment
spoonacular_api_key = os.getenv("spoonacular_api_key")
postgres_connection_string = os.getenv("POSTGRES_CONNECTION_STRING", "postgresql://user:password@postgres:5432/mychef_db")
swiggy_access_token = os.getenv("SWIGGY_ACCESS_TOKEN", "")

# Resolve npx path: nvm installs aren't always on PATH when spawned from Python
_npx_path = shutil.which("npx")
if not _npx_path:
    # Common nvm location on macOS
    _nvm_npx = os.path.expanduser("~/.nvm/versions/node/v22.14.0/bin/npx")
    if os.path.isfile(_nvm_npx):
        _npx_path = _nvm_npx
    else:
        _npx_path = "npx"  # fallback, works inside Docker where node is on PATH

# Build a clean env dict that includes the nvm node bin dir on PATH
def _build_env(**extra):
    env = os.environ.copy()
    npx_dir = os.path.dirname(_npx_path)
    if npx_dir and npx_dir not in env.get("PATH", ""):
        env["PATH"] = npx_dir + os.pathsep + env.get("PATH", "")
    env.update(extra)
    return env

# Setup Spoonacular MCP connection
spoonacular_params = StdioServerParameters(
    command=_npx_path,
    args=["-y", "spoonacular-mcp"],
    env=_build_env(SPOONACULAR_API_KEY=spoonacular_api_key or "")
)
spoonacular_toolset = McpToolset(connection_params=StdioConnectionParams(server_params=spoonacular_params))

# Setup PostgreSQL MCP connection
postgres_params = StdioServerParameters(
    command=_npx_path,
    args=["-y", "mcp-postgres"],
    env=_build_env(DATABASE_URL=postgres_connection_string)
)
postgres_toolset = McpToolset(connection_params=StdioConnectionParams(server_params=postgres_params))

# Setup Swiggy MCP connections (Instamart, Food, Dineout)
swiggy_headers = {"Authorization": f"Bearer {swiggy_access_token}"} if swiggy_access_token else {}

swiggy_im_params = StreamableHTTPConnectionParams(
    url="https://mcp.swiggy.com/im",
    headers=swiggy_headers
)
swiggy_im_toolset = McpToolset(connection_params=swiggy_im_params)

swiggy_food_params = StreamableHTTPConnectionParams(
    url="https://mcp.swiggy.com/food",
    headers=swiggy_headers
)
swiggy_food_toolset = McpToolset(connection_params=swiggy_food_params)

swiggy_dineout_params = StreamableHTTPConnectionParams(
    url="https://mcp.swiggy.com/dineout",
    headers=swiggy_headers
)
swiggy_dineout_toolset = McpToolset(connection_params=swiggy_dineout_params)


model_name = "openai/gpt-oss:120b-cloud"

# Worker 1: Diet Manager
diet = Agent(
    model=model_name,
    name='Diet',
    description="Fetches family dietary profiles, allergies, and pantry data from the database (Read-Only).",
    instruction=DIET_INSTRUCTION,
    tools=[postgres_toolset, spoonacular_toolset],
)

# Worker 2: Recipe Finder
recipe = Agent(
    model=model_name,
    name='Recipe',
    description="Finds recipes from Spoonacular and calculates missing ingredient gaps.",
    instruction=RECIPE_INSTRUCTION,
    tools=[spoonacular_toolset, postgres_toolset],
)

# Worker 3: Shopper
shopper = Agent(
    model=model_name,
    name='Shopper',
    description="Handles Swiggy procurement — prices items and executes orders.",
    instruction=SHOPPER_INSTRUCTION,
    tools=[postgres_toolset, swiggy_im_toolset, swiggy_food_toolset, swiggy_dineout_toolset],
)

# Worker 4: Budget Calculator
budget = Agent(
    model=model_name,
    name='Budget',
    description="Calculates savings and financial comparisons.",
    instruction=BUDGET_INSTRUCTION,
    tools=[],
)

# Orchestrator: Chef
chef = Agent(
    model=model_name,
    name='Chef',
    description="The main coordinator that delegates tasks and presents results.",
    instruction=CHEF_INSTRUCTION,
    sub_agents=[diet, recipe, shopper, budget],
)

if __name__ == "__main__":
    print("MyChef Agent initialized. Run 'adk web' to start the web interface.")
agent = chef
root_agent = chef
