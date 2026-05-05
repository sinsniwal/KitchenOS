"""
Test suite for Ollama / LLM integration.

Verifies that the local Ollama instance is reachable and that the
openai/gpt-oss:120b-cloud model string is correctly routed through litellm.
"""
import os
import pytest
import httpx

# Ensure Ollama env vars are set before any ADK imports
os.environ.setdefault("OPENAI_BASE_URL", "http://localhost:11434/v1")
os.environ.setdefault("OPENAI_API_KEY", "ollama")


# ---------------------------------------------------------------------------
# Ollama health / availability
# ---------------------------------------------------------------------------

def test_ollama_is_running():
    """Ollama API should be reachable on localhost:11434."""
    try:
        resp = httpx.get("http://localhost:11434/api/version", timeout=5)
        data = resp.json()
        print(f"[Ollama] version: {data.get('version')}")
        assert resp.status_code == 200
    except httpx.ConnectError:
        pytest.fail("Ollama is not running on localhost:11434")


def test_ollama_has_target_model():
    """The gpt-oss:120b-cloud model tag should exist in Ollama."""
    resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
    models = [m["name"] for m in resp.json().get("models", [])]
    print(f"[Ollama] available models: {models}")
    assert "gpt-oss:120b-cloud" in models, (
        f"gpt-oss:120b-cloud not found in Ollama. Available: {models}"
    )


# ---------------------------------------------------------------------------
# LiteLLM routing (the layer google-adk uses for openai/* models)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_litellm_completion_to_ollama():
    """litellm.acompletion should route openai/gpt-oss:120b-cloud to Ollama."""
    import litellm

    response = await litellm.acompletion(
        model="openai/gpt-oss:120b-cloud",
        messages=[{"role": "user", "content": "Reply with just the word HELLO"}],
        api_base="http://localhost:11434/v1",
        api_key="ollama",
    )
    text = response.choices[0].message.content
    print(f"[LiteLLM] response: {text}")
    assert response is not None
    assert len(text.strip()) > 0, "Model returned empty response"


@pytest.mark.asyncio
async def test_litellm_streaming_to_ollama():
    """litellm streaming should also work for the Ollama endpoint."""
    import litellm

    chunks = []
    response = await litellm.acompletion(
        model="openai/gpt-oss:120b-cloud",
        messages=[{"role": "user", "content": "Say OK"}],
        api_base="http://localhost:11434/v1",
        api_key="ollama",
        stream=True,
    )
    async for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            chunks.append(delta)
    full = "".join(chunks)
    print(f"[LiteLLM streaming] response: {full}")
    assert len(full.strip()) > 0, "Streaming returned empty content"


# ---------------------------------------------------------------------------
# Agent model config sanity
# ---------------------------------------------------------------------------

def test_agent_model_uses_openai_prefix():
    """Chef agent model string must start with 'openai/' for litellm routing."""
    from agents.head_chef.agent import chef
    model = chef.model
    print(f"[Agent] model: {model}")
    assert str(model).startswith("openai/"), (
        f"Agent model must use 'openai/' prefix for litellm, got: {model}"
    )
