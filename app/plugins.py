from google.adk.plugins.base_plugin import BasePlugin
from typing import Any

class LoggerPlugin(BasePlugin):
    def __init__(self) -> None:
        super().__init__(name="logger")

    async def before_agent_callback(self, *, agent: Any, callback_context: Any) -> None:
        """Fires before the agent handles a message."""
        sid = getattr(callback_context, "session_id", "")
        uid = getattr(callback_context, "user_id", "")
        rid = getattr(callback_context, "request_id", "")
        print(f"[ADK][agent:start] {agent.name} | session_id={sid} user_id={uid} request_id={rid}")

    async def after_model_callback(
        self, *, callback_context: Any, llm_response: Any
    ) -> None:
        model = getattr(callback_context, "agent_name", "?")
        finish = getattr(llm_response, "finish_reason", "?")
        print(f"[ADK][model:after] agent={model} finish_reason={finish}")

    async def after_agent_callback(self, *, agent: Any, callback_context: Any) -> None:
        """Fires after the agent produces a final response."""
        sid = getattr(callback_context, "session_id", "")
        uid = getattr(callback_context, "user_id", "")
        rid = getattr(callback_context, "request_id", "")
        print(f"[ADK][agent:end] {agent.name} | session_id={sid} user_id={uid} request_id={rid}")
