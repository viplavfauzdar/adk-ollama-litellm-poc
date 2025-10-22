import json
from typing import Any, Optional

from google.adk.plugins.base_plugin import BasePlugin
from google.genai import types

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

    async def before_tool_callback(
        self, *, tool: Any, tool_args: dict, tool_context: Any
    ) -> None:
        print(f"[ADK][tool:start] {getattr(tool, 'name', tool)} args={tool_args}")

    async def after_tool_callback(
        self, *, tool: Any, tool_args: dict, tool_context: Any, result: dict
    ) -> None:
        print(f"[ADK][tool:end] {getattr(tool, 'name', tool)} result={result}")


class OllamaToolCallBridgePlugin(BasePlugin):
    """Translates plain-text JSON tool calls from Ollama into structured calls.

    Some Ollama models emit `{"name": "...", "arguments": {...}}` as plain text
    instead of using the tool-calling protocol. This plugin converts those blobs
    into `FunctionCall` parts so ADK can execute the tool and continue the flow.
    """

    def __init__(self, *, allowed_tool_names: Optional[set[str]] = None) -> None:
        super().__init__(name="ollama_tool_call_bridge")
        if allowed_tool_names is None:
            self._allowed_tool_names = None
        else:
            self._allowed_tool_names = {
                name for name in allowed_tool_names if isinstance(name, str)
            }
        self._last_tool_text: Optional[str] = None

    async def before_model_callback(
        self, *, callback_context: Any, llm_request: Any
    ) -> None:
        contents = getattr(llm_request, "contents", None)
        if not contents:
            return

        allowed_names = (
            self._allowed_tool_names
            if self._allowed_tool_names is not None
            else self._derive_allowed_tool_names(callback_context)
        )
        if not allowed_names:
            return

        for content in contents:
            if not getattr(content, "parts", None):
                continue
            new_parts = []
            content_mutated = False
            for part in content.parts:
                replaced, keep_original, _ = self._maybe_convert_part(
                    part, allowed_names, for_request=True
                )
                if replaced is not None:
                    new_parts.append(replaced)
                    content_mutated = True
                elif keep_original:
                    new_parts.append(part)
                else:
                    content_mutated = True
            if content_mutated:
                content.parts = new_parts

    async def after_model_callback(
        self, *, callback_context: Any, llm_response: Any
    ) -> None:
        content = getattr(llm_response, "content", None)
        if not content or not content.parts:
            return
        parts_desc = []
        for idx, part in enumerate(content.parts):
            if part.text:
                parts_desc.append(f"{idx}:text={part.text[:80]!r}")
            elif part.function_call:
                parts_desc.append(f"{idx}:function_call={part.function_call.name}")
            elif part.function_response:
                parts_desc.append(f"{idx}:function_response={part.function_response.name}")
            else:
                parts_desc.append(f"{idx}:{type(part)}")
        print(
            "[ADK][ollama-bridge] received"
            f" {len(content.parts)} part(s); finish={getattr(llm_response, 'finish_reason', None)};"
            f" parts={'; '.join(parts_desc)}"
        )

        allowed_names = (
            self._allowed_tool_names
            if self._allowed_tool_names is not None
            else self._derive_allowed_tool_names(callback_context)
        )
        print(f"[ADK][ollama-bridge] allowed tool names: {allowed_names}")
        if not allowed_names:
            print("[ADK][ollama-bridge] no allowed tool names; skipping conversion")
            return

        mutated = False
        new_parts = []
        finish_override = None
        for part in content.parts:
            converted, keep_original, part_finish_override = self._maybe_convert_part(
                part, allowed_names
            )
            if part_finish_override is not None:
                finish_override = part_finish_override
            if converted is not None:
                new_parts.append(converted)
                mutated = True
                part_desc = getattr(converted.function_call, "name", None) or getattr(converted, "text", "")
                print(f"[ADK][ollama-bridge] converted part -> {part_desc!r}")
            elif keep_original:
                new_parts.append(part)
            else:
                mutated = True  # text part suppressed
                print("[ADK][ollama-bridge] suppressed unsupported part")

        if mutated:
            llm_response.content = types.Content(
                role=content.role,
                parts=new_parts,
            )
        if finish_override is not None:
            llm_response.finish_reason = finish_override
            llm_response.partial = False
            llm_response.turn_complete = True
            print(f"[ADK][ollama-bridge] forcing finish_reason={finish_override}")

    def _maybe_convert_part(
        self, part: types.Part, allowed_names: set[str], *, for_request: bool = False
    ) -> tuple[Optional[types.Part], bool, Optional[types.FinishReason]]:
        if part.function_call:
            if for_request:
                return None, True, None
            return self._handle_function_call_part(part, allowed_names)
        if part.function_response:
            return self._handle_function_response_part(
                part, allowed_names, for_request=for_request
            )
        if for_request:
            return None, True, None
        text = getattr(part, "text", None)
        if not text:
            return None, True, None

        text = text.strip()
        if not text.startswith("{"):
            return None, True, None

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return None, True, None

        if not isinstance(payload, dict):
            return None, True, None

        name = payload.get("name")
        if not isinstance(name, str):
            return None, True, None

        args = payload.get("arguments", {}) or {}
        if not isinstance(args, dict):
            message = (
                f"Ollama emitted malformed tool arguments for '{name}'; ignoring them."
            )
            return types.Part(text=message), False, types.FinishReason.STOP

        if name in {"response", "agent_response", "root"}:
            text_payload = (
                args.get("text")
                or args.get("response")
                or args.get("message")
                or args.get("content")
            )
            if isinstance(text_payload, str):
                return types.Part(text=text_payload), False, types.FinishReason.STOP
            if isinstance(text_payload, list):
                try:
                    text_payload = " ".join(str(part) for part in text_payload)
                    return types.Part(text=text_payload), False, types.FinishReason.STOP
                except Exception:
                    pass
            # No usable text; treat as unsupported tool below.

        if name not in allowed_names:
            message = (
                f"Ollama emitted unsupported tool call '{name}'; ignoring it."
            )
            return types.Part(text=message), False, types.FinishReason.STOP

        call = types.FunctionCall(
            name=name,
            args=args,
            id=payload.get("id"),
        )
        return types.Part(function_call=call), False, None

    def _handle_function_call_part(
        self, part: types.Part, allowed_names: set[str]
    ) -> tuple[Optional[types.Part], bool, Optional[types.FinishReason]]:
        call = part.function_call
        if call is None or not call.name:
            return None, True, None

        name = call.name
        args = call.args or {}

        if name in {"response", "agent_response", "root"}:
            text_payload = (
                args.get("text")
                or args.get("response")
                or args.get("message")
                or args.get("content")
            )
            if isinstance(text_payload, str):
                return types.Part(text=text_payload), False, types.FinishReason.STOP
            if isinstance(text_payload, list):
                try:
                    text_payload = " ".join(str(part) for part in text_payload)
                    return types.Part(text=text_payload), False, types.FinishReason.STOP
                except Exception:
                    pass
            if args:
                try:
                    text_payload = json.dumps(args, ensure_ascii=False)
                except Exception:
                    text_payload = str(args)
                return types.Part(text=text_payload), False, types.FinishReason.STOP
            if self._last_tool_text:
                return types.Part(text=self._last_tool_text), False, types.FinishReason.STOP
            # fall back to unsupported handling below

        if name not in allowed_names:
            message = (
                f"Ollama emitted unsupported tool call '{name}'; ignoring it."
            )
            return types.Part(text=message), False, types.FinishReason.STOP
        return None, True, None

    def _handle_function_response_part(
        self, part: types.Part, allowed_names: set[str], *, for_request: bool = False
    ) -> tuple[Optional[types.Part], bool, Optional[types.FinishReason]]:
        response = part.function_response
        if response is None or not response.name:
            return None, True, None
        name = response.name
        if name not in allowed_names:
            return None, True, None
        payload = response.response
        if payload is None:
            text_payload = f"{name} completed."
        elif isinstance(payload, dict):
            if "output" in payload:
                text_payload = str(payload["output"])
            elif "result" in payload:
                text_payload = str(payload["result"])
            else:
                try:
                    text_payload = json.dumps(payload, ensure_ascii=False)
                except Exception:
                    text_payload = str(payload)
        else:
            text_payload = str(payload)

        print(f"[ADK][ollama-bridge] tool '{name}' response payload -> {text_payload!r}")
        final_text = f"{name} result: {text_payload}"
        self._last_tool_text = final_text
        finish = None if for_request else types.FinishReason.STOP
        return types.Part(text=final_text), False, finish

    def _derive_allowed_tool_names(self, callback_context: Any) -> set[str]:
        agent = getattr(callback_context, "agent", None)
        tools = getattr(agent, "tools", None)
        if not tools:
            return set()
        names: set[str] = set()
        for tool in tools:
            candidate = getattr(tool, "name", None)
            if isinstance(candidate, str):
                names.add(candidate)
                continue
            candidate = getattr(tool, "__name__", None)
            if isinstance(candidate, str):
                names.add(candidate)
        return names
