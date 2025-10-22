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

The Dev UI gives you a full run transcript:
- Conversation pane: prompts and responses rendered in chat format with streaming updates.
- Tool call inspector: every tool invocation (`calc`, `http_get`) with its arguments and JSON result.
- Event timeline: raw ADK events (model responses, tool responses, plugin output) so you can debug loops or hallucinated tools.
- Session/state sidebar: current session variables, plugins, and agent metadata.

Use the refresh arrow beside an event to replay from that point, or “New chat” to clear the session and start fresh.

## What’s inside
- `LlmAgent` with `LiteLlm(model=f"ollama_chat/{OLLAMA_MODEL}")`
- Three Python tools registered directly on the agent:
  - `calc` for arithmetic
  - `http_get` for resilient JSON fetches
  - `weather_by_zip` (zippopotam.us + Open-Meteo) for current weather by US ZIP
- Simple logger plugin plus an Ollama compatibility plugin to coerce plain JSON
  tool call text into proper ADK function calls

## What is Google ADK?
The **Agent Development Kit (ADK)** is Google’s framework for composing AI “agents” that can call tools, manage sessions, and plug into custom backends (LLMs, memory stores, auth flows, etc.). Key responsibilities in this repo:
- **Runner lifecycle**: `Runner` (from `google.adk.runners`) orchestrates sessions, invokes our agent, and emits ADK events that power the CLI and the Dev UI.
- **Agent model**: `LlmAgent` (app/agents.py) is an ADK agent class; ADK handles prompt assembly, tool registration, and response post-processing.
- **Tool / plugin wrappers**: ADK auto-wraps Python functions into callable tools and lets us hook custom plugins (app/plugins.py) into the execution pipeline.
- **App glue**: `App` (app/__init__.py) bundles the root agent plus plugins so commands like `adk web agents` can discover and serve the configuration.

In practice, ADK provides the agent framework; LiteLlm tells ADK how to reach Ollama; our code supplies the concrete tools, instructions, and plugins that define the agent’s behaviour.

```
Google ADK stack (this project)
┌─────────────────────────────────────────┐
│ ADK Web / CLI                          │
│  • loads App from app/__init__.py      │
│  • instantiates Runner                 │
└─────────────────┬──────────────────────┘
                  │
┌─────────────────▼──────────────────────┐
│ Runner (google.adk.runners.Runner)     │
│  • manages sessions & plugins          │
│  • calls root_agent on each message    │
└─────────────────┬──────────────────────┘
                  │
┌─────────────────▼──────────────────────┐
│ root_agent (LlmAgent)                  │
│  • LiteLlm → Ollama backend            │
│  • tools: calc, http_get, weather_by_zip│
│  • plugins log/bridge tool responses   │
└─────────────────┬──────────────────────┘
                  │
        ┌─────────▼──────────┐
        │ LiteLlm / Ollama    │
        │  • sends prompts    │
        │  • emits tool calls │
        └─────────┬──────────┘
                  │
        ┌─────────▼──────────┐
        │ Python tools        │
        │  app/tools.py       │
        │  • calc             │
        │  • http_get         │
        │  • weather_by_zip   │
        └─────────────────────┘
```

## Architecture overview
```
adk-ollama-litellm-poc/
├─ app/
│  ├─ main.py         → CLI runner. Creates sessions, injects a user message, prints the final answer.
│  ├─ agents.py       → Declares the root LlmAgent, wires it to LiteLlm/Ollama, and registers calc/http_get.
│  │                    Also exposes the weather_by_zip tool alongside calc/http_get.
│  ├─ tools.py        → Plain Python implementations of the calc and http_get tools.
│  ├─ plugins.py      → LoggerPlugin (prints lifecycle events) and OllamaToolCallBridgePlugin (fixes Ollama JSON/tool-call quirks).
│  └─ __init__.py     → Builds the ADK App object so adk web / runners can load the agent and plugins.
└─ README.md, requirements, tests, etc.
```

**Runtime flow**
```
user prompt
   │
   ▼
Runner (app/main.py) ──→ root_agent (app/agents.py)
   │                        │
   │                        ├─ uses LiteLlm to call the Ollama daemon
   │                        └─ invokes tools from app/tools.py when the model requests them
   │
   ▼
LoggerPlugin + OllamaToolCallBridgePlugin (app/plugins.py)
   │
   ▼
ADK events → CLI output or the ADK web UI
```

LiteLlm is the bridge between ADK and the local Ollama server (`http://localhost:11434`). The helper plugin rewrites any plain-text tool call JSON that llama3 emits so ADK can execute the correct Python function and feed the result back to the model.

To try the weather workflow, ask the assistant something like “What’s the weather for 94107?”—the agent will call `weather_by_zip`, then summarize the live conditions in °F with wind details.
