from google.adk.apps.app import App

from app.agents import root_agent
from app.plugins import LoggerPlugin, OllamaToolCallBridgePlugin


def _collect_tool_names(agent) -> set[str]:
    names: set[str] = set()
    for tool in getattr(agent, "tools", []):
        name = getattr(tool, "name", getattr(tool, "__name__", None))
        if not isinstance(name, str):
            continue
        if name == agent.name:
            continue
        names.add(name)

    for child in getattr(agent, "sub_agents", []) or []:
        names.update(_collect_tool_names(child))

    return names


def _discover_tool_names() -> set[str]:
    return _collect_tool_names(root_agent)


app = App(
    name="app",
    root_agent=root_agent,
    plugins=[
        OllamaToolCallBridgePlugin(allowed_tool_names=_discover_tool_names()),
        LoggerPlugin(),
    ],
)

__all__ = ["app"]
