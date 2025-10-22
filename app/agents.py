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

weather_agent = LlmAgent(
    name="weather",
    model=ollama_llm,
    instruction=(
        "You are a weather specialist. Users provide a US ZIP code and you call the weather_by_zip tool "
        "exactly once to fetch current conditions. If the ZIP is missing or invalid, ask for a valid 5-digit "
        "US ZIP code. Summarize the temperature in °F, mention notable wind details, and cite the observation time."
    ),
    tools=[weather_by_zip],
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)

root_agent = LlmAgent(
    name="root",
    model=ollama_llm,
    instruction=(
        "You are a helpful assistant running on a local Ollama model. "
        "Always produce a final textual answer in plain language. "
        "Use tools like calc and http_get when helpful. If a tool returns ok=False or errors, "
        "explain the failure briefly and continue with the rest of the task. "
        "For weather requests that mention a US ZIP code, hand the conversation to the weather agent. "
        "The only tools you may call directly are calc and http_get—never invent other tool names. "
        "When you need to perform multiple operations, call calc and http_get separately and combine "
        "their outputs yourself in the final answer. Keep answers concise and never emit raw JSON in your final answer."
    ),
    tools=[calc, http_get],
    sub_agents=[weather_agent],
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)
