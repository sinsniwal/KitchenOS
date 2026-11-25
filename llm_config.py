import os
from dotenv import load_dotenv

load_dotenv()

# Select provider: 'ollama' or 'openai'
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()

if LLM_PROVIDER == "openai":
    model_env = os.getenv("CUSTOM_OPENAI_MODEL_NAME", "gpt-4o")
    # Prefix with openai/ to force LiteLLM routing, bypassing ADK's regex checks for new models
    if not model_env.startswith("openai/"):
        MODEL_NAME = f"openai/{model_env}"
    else:
        MODEL_NAME = model_env
elif LLM_PROVIDER == "ollama":
    MODEL_NAME = os.getenv("OLLAMA_MODEL_NAME", "openai/gpt-oss:120b-cloud")
else:
    MODEL_NAME = "openai/gpt-oss:120b-cloud"
