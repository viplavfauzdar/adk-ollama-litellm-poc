from google.adk.apps.app import App

from app.agents import root_agent
from app.plugins import LoggerPlugin

app = App(
    name="app",
    root_agent=root_agent,
    plugins=[LoggerPlugin()],
)

__all__ = ["app"]
