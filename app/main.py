from typing import Any, Dict
import httpx
import time

def calc(expression: str) -> str:
    """Evaluate a simple arithmetic expression, e.g., '12*(3+4)'. POC only."""
    return str(eval(expression, {"__builtins__": {}}))

def http_get(url: str, *, retries: int = 3, timeout: float = 10.0) -> Dict[str, Any]:
    """GET a JSON endpoint and return parsed JSON with resilient behavior.

    Returns a dict with keys: ok (bool), status (int|None), data (Any|None), error (str|None).
    """
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.get(url)
                status = r.status_code
                if 200 <= status < 300:
                    try:
                        return {"ok": True, "status": status, "data": r.json(), "error": None}
                    except Exception as parse_err:
                        return {"ok": False, "status": status, "data": None, "error": f"JSON parse error: {parse_err}"}
                else:
                    # Non-2xx: capture and (optionally) retry if 5xx
                    if 500 <= status < 600 and attempt < retries:
                        time.sleep(0.5 * attempt)
                        continue
                    return {"ok": False, "status": status, "data": None, "error": f"HTTP {status}: {r.text[:300]}"}
        except Exception as e:
            last_err = e
            # Retry on transient network errors
            if attempt < retries:
                time.sleep(0.5 * attempt)
                continue
    return {"ok": False, "status": None, "data": None, "error": str(last_err) if last_err else "Unknown error"}

import asyncio
import os
from importlib import import_module
import google.genai.types as types
from google.adk.runners import Runner
from app.agents import root_agent
from app.plugins import LoggerPlugin

APP_NAME = "app"
USER_ID = os.getenv("ADK_USER_ID", "local-user")
SESSION_ID = os.getenv("ADK_SESSION_ID", "local-session")

def make_session_service():
    """
    Try several file-backed session services so the Dev UI (adk web) can see
    the same sessions. Falls back to InMemory if none exist.
    """
    try:
        sess_mod = import_module("google.adk.sessions")
    except Exception:
        from google.adk.sessions import InMemorySessionService
        return InMemorySessionService()

    candidates = [
        ("LocalFileSessionService", {"base_dir": ".adk_data"}),
        ("FileSessionService", {"base_dir": ".adk_data"}),
        ("SqliteSessionService", {"db_path": ".adk_data/adk.db"}),
    ]
    for cls_name, kwargs in candidates:
        cls = getattr(sess_mod, cls_name, None)
        if cls:
            return cls(**kwargs)

    # last resort
    InMemory = getattr(sess_mod, "InMemorySessionService")
    return InMemory()

async def run_local_agent_async(message: str):
    session_service = make_session_service()
    # Ensure the session exists
    await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
        plugins=[LoggerPlugin()],
    )

    # User message as ADK Content
    content = types.Content(role="user", parts=[types.Part(text=message)])

    got_final = False
    async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
        if hasattr(event, "is_final_response") and event.is_final_response():
            got_final = True
            print("\n=== FINAL ANSWER ===")
            try:
                print(event.content.parts[0].text)
            except Exception:
                print(event)

    if not got_final:
        print("\n(No final response event received.)")

if __name__ == "__main__":
    msg = os.getenv(
        "ADK_TEST_MSG",
        "First compute 2*(5+7) with the calc tool. Then fetch https://jsonplaceholder.typicode.com/todos/1 with http_get and summarize the title.",
    )
    asyncio.run(run_local_agent_async(msg))