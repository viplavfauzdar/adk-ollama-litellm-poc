import os
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from app.tools import calc, http_get, weather_by_zip

OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:8b")

# Ensure ADK treats this as a chat model and knows where Ollama lives
ollama_llm = LiteLlm(
    model=f"ollama_chat/{OLLAMA_MODEL}",
    api_base=OLLAMA_API_BASE,
)

root_agent = LlmAgent(
    name="root",
    model=ollama_llm,
    instruction=(
        "You are a helpful assistant running on a local Ollama model. "
        "Always produce a final textual answer in plain language. "
        "You may call exactly three tools: calc, http_get, and weather_by_zip. "
        "Use calc for arithmetic, http_get for JSON APIs, and weather_by_zip for current weather by US ZIP code "
        "(ask the user for a 5-digit ZIP if you do not have one). "
        "If any tool returns ok=False or errors, explain the issue briefly and continue. "
        "Never invent new tool names, never emit raw JSON in the final answer, and keep responses concise."
    ),
    tools=[calc, http_get, weather_by_zip],
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)
