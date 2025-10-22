import os
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from app.tools import calc, http_get

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:8b")

root_agent = LlmAgent(
    name="root",
    model=LiteLlm(model=f"ollama_chat/{OLLAMA_MODEL}"),
    instruction=(
    "You are a helpful assistant. "
    "Use tools when they help. If a tool returns ok=False or errors, "
    "explain the failure briefly and continue with the rest of the task. "
    "Keep answers concise."
    ),
    tools=[calc, http_get],
)
