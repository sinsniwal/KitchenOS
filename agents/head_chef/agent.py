import os
import asyncio
import shutil
from dotenv import load_dotenv

from google.adk.agents.llm_agent import Agent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams, StreamableHTTPConnectionParams
from mcp.client.stdio import StdioServerParameters

from google.adk.flows.llm_flows import functions
original_get_tool = functions._get_tool
def patched_get_tool(function_call, tools_dict):
    if hasattr(function_call, 'name') and function_call.name.startswith("functions/"):
        function_call.name = function_call.name.replace("functions/", "", 1)
    return original_get_tool(function_call, tools_dict)
functions._get_tool = patched_get_tool

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
spoonacular_api_key = os.getenv("SPOONACULAR_API_KEY")
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
    args=["spoonacular-mcp"],
    env=_build_env(SPOONACULAR_API_KEY=spoonacular_api_key or "")
)
spoonacular_toolset = McpToolset(connection_params=StdioConnectionParams(server_params=spoonacular_params))

# Setup PostgreSQL MCP connection
postgres_params = StdioServerParameters(
    command=_npx_path,
    args=["mcp-postgres"],
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


import sys
# Add root path to sys.path so we can import llm_config
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from llm_config import MODEL_NAME

model_name = MODEL_NAME

# Worker 1: Diet Manager
diet = Agent(
    model=model_name,
    name='Diet',
    description="Fetches family dietary profiles, allergies, and pantry data from the database. READ-ONLY access. Use this agent when you need to know what the family eats, their allergies, and what is currently in the pantry.",
    instruction=DIET_INSTRUCTION,
    tools=[postgres_toolset, spoonacular_toolset],
)

# Worker 2: Recipe Finder
recipe = Agent(
    model=model_name,
    name='Recipe',
    description="Finds recipes from Spoonacular API and calculates missing ingredient gaps vs the pantry. Use this agent after you have dietary profiles and pantry data from Diet.",
    instruction=RECIPE_INSTRUCTION,
    tools=[spoonacular_toolset, postgres_toolset],
)

shopper_tools = [postgres_toolset]
if swiggy_access_token:
    shopper_tools.extend([swiggy_im_toolset, swiggy_food_toolset, swiggy_dineout_toolset])

# Worker 3: Shopper
shopper = Agent(
    model=model_name,
    name='Shopper',
    description="Prices and orders items on Swiggy Instamart, searches restaurants on Swiggy Food/Dineout, and writes to the Postgres pantry ledger. Use this agent when you need real prices or need to place an order.",
    instruction=SHOPPER_INSTRUCTION,
    tools=shopper_tools,
)

# Worker 4: Budget Calculator
budget = Agent(
    model=model_name,
    name='Budget',
    description="Calculates financial savings of cooking at home vs ordering delivery. No tools needed — pure calculation. Use this agent after you have Swiggy prices from Shopper.",
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
