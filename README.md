# ADK + Ollama via LiteLLM (POC)

Minimal **Google ADK** agent using **LiteLLM** to talk to **Ollama** (e.g., `gpt-oss:20b`) with tool calling.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Make sure Ollama is running locally
# Point LiteLLM/ADK to Ollama (ADK docs recommend OLLAMA_API_BASE)
export OLLAMA_API_BASE=http://localhost:11434
# Keep your model preference (defaults to gpt-oss:20b)
export OLLAMA_MODEL=gpt-oss:20b

# Run
python -m app.main
```
> Per ADK docs, **use the `ollama_chat` provider** for tool-enabled agents. (`openai` provider also works with OPENAI_API_BASE=http://localhost:11434/v1, but `ollama_chat` is preferred.)

## Interactive UI with ADK Web
```bash
# With the virtualenv active and environment variables set (see above):
adk web agents
```
Then open the printed URL (defaults to http://127.0.0.1:8000) and choose the `interactive` agent to chat with the app.

## What’s inside
- `LlmAgent` with `LiteLlm(model=f"ollama_chat/{OLLAMA_MODEL}")`
- Two function tools: `calc`, `http_get` (auto-wrapped by ADK)
- Simple logger plugin
