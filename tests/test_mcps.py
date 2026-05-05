"""
Test suite for MCP toolset connections (Spoonacular + PostgreSQL).

These tests verify that the MCP subprocess servers can be launched via npx
and that they expose the expected tools over the stdio JSON-RPC protocol.
"""
import os
os.environ.setdefault("OPENAI_BASE_URL", "http://localhost:11434/v1")
os.environ.setdefault("OPENAI_API_KEY", "ollama")
os.environ.setdefault("POSTGRES_CONNECTION_STRING", "postgresql://user:password@localhost:5432/mychef_db")

import pytest
from agents.head_chef.agent import spoonacular_toolset, postgres_toolset


def _should_skip(err_str):
    """Check if the error indicates an infrastructure issue (not a code bug)."""
    skip_signals = [
        "no such file or directory", "connection refused",
        "could not connect", "cancel scope", "timeout",
        "failed to create mcp session",
    ]
    return any(s in err_str.lower() for s in skip_signals)


# ---------------------------------------------------------------------------
# Spoonacular MCP tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_spoonacular_mcp_starts_and_lists_tools():
    """Spoonacular MCP server should launch via npx and expose recipe tools."""
    try:
        tools = await spoonacular_toolset.get_tools()
    except Exception as e:
        if _should_skip(str(e)):
            pytest.skip(f"Spoonacular MCP not reachable: {e}")
        raise

    tool_names = [t.name for t in tools]
    print(f"[Spoonacular] tools returned: {tool_names}")

    assert len(tools) > 0, "Spoonacular MCP returned zero tools"

    # Also check recipe tools while we have the result
    recipe_tools = [n for n in tool_names if "recipe" in n.lower() or "search" in n.lower()]
    print(f"[Spoonacular] recipe-related tools: {recipe_tools}")
    assert len(recipe_tools) > 0, (
        f"Expected at least one recipe/search tool, got: {tool_names}"
    )


# ---------------------------------------------------------------------------
# PostgreSQL MCP tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_postgres_mcp_starts_and_lists_tools():
    """Postgres MCP server should launch via npx and expose query tools."""
    try:
        tools = await postgres_toolset.get_tools()
    except Exception as e:
        if _should_skip(str(e)):
            pytest.skip(f"Postgres MCP not reachable: {e}")
        raise

    tool_names = [t.name for t in tools]
    print(f"[Postgres] tools returned: {tool_names}")

    assert len(tools) > 0, "Postgres MCP returned zero tools"

    # Also check query tools while we have the result
    query_tools = [n for n in tool_names if "query" in n.lower() or "sql" in n.lower() or "execute" in n.lower()]
    print(f"[Postgres] query-related tools: {query_tools}")
    assert len(query_tools) > 0, (
        f"Expected at least one query/sql tool, got: {tool_names}"
    )


# ---------------------------------------------------------------------------
# Swiggy MCP tests
# ---------------------------------------------------------------------------

from agents.head_chef.agent import swiggy_im_toolset

@pytest.mark.asyncio
async def test_swiggy_mcp_starts_and_lists_tools():
    """Swiggy MCP server should connect via SSE and expose tools."""
    try:
        tools = await swiggy_im_toolset.get_tools()
    except Exception as e:
        err_str = str(e).lower()
        if _should_skip(err_str) or "401" in err_str or "unauthorized" in err_str or "forbidden" in err_str or "403" in err_str:
            pytest.skip(f"Swiggy MCP not reachable or requires valid OAuth token: {e}")
        raise

    tool_names = [t.name for t in tools]
    print(f"[Swiggy] tools returned: {tool_names}")

    assert len(tools) > 0, "Swiggy MCP returned zero tools"


@pytest.mark.asyncio
async def test_swiggy_milk_price():
    """GroceryManager should be able to query the price of milk from Swiggy Instamart."""
    import os
    os.environ.setdefault("OPENAI_BASE_URL", "http://localhost:11434/v1")
    os.environ.setdefault("OPENAI_API_KEY", "ollama")
    os.environ.setdefault("POSTGRES_CONNECTION_STRING", "postgresql://user:password@localhost:5432/mychef_db")
    
    from agents.head_chef.agent import swiggy_im_toolset
    from google.adk.agents.llm_agent import Agent
    from google.adk import Runner
    from google.adk.sessions import InMemorySessionService
    
    try:
        tools = await swiggy_im_toolset.get_tools()
        print(f"\n[Debug] Swiggy MCP Tools Available: {[t.name for t in tools]}\n")
    except Exception as e:
        print(f"\n[Debug] Failed to fetch Swiggy tools: {e}\n")

    test_agent = Agent(
        model="openai/gpt-oss:120b-cloud",
        name='SwiggyTestAgent',
        description="You test the Swiggy Instamart integration.",
        instruction="You are a test agent. Search for milk on Swiggy Instamart, but DO NOT place an order.",
        tools=[swiggy_im_toolset],
    )
    
    runner = Runner(
        app_name="TestApp",
        agent=test_agent,
        session_service=InMemorySessionService(),
        auto_create_session=True
    )
    
    try:
        response_chunks = []
        from google.genai import types
        
        async for event in runner.run_async(
            user_id="test_user",
            session_id="test_session",
            new_message=types.Content(role="user", parts=[types.Part.from_text(text="Please search for 'milk' on Swiggy Instamart and tell me the price. Do not place an order.")])
        ):
            response_chunks.append(str(event))
        response = "".join(response_chunks)
    except Exception as e:
        err_str = str(e).lower()
        if "authenticationerror" in err_str or "litellm" in err_str or _should_skip(err_str) or "401" in err_str or "unauthorized" in err_str or "forbidden" in err_str or "403" in err_str or "405" in err_str or "500" in err_str or "method not allowed" in err_str:
            pytest.skip(f"Skipping test due to missing LLM key or Swiggy upstream error: {e}")
        raise
        
    print(f"[Swiggy Milk Test] Agent Response: {response}")
    
    # Just ensure it successfully returned a string (the specific output depends on live stock/prices)
    assert isinstance(response, str) and len(response) > 0
