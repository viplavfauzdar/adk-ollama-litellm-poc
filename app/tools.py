from typing import Any, Dict
import httpx
import time

def calc(expression: str) -> str:
    """Evaluate a simple arithmetic expression, e.g., '12*(3+4)'. POC only."""
    return str(eval(expression, {"__builtins__": {}}))  # POC only

def http_get(url: str, *, retries: int = 3, timeout: float = 10.0) -> Dict[str, Any]:
    """GET a JSON endpoint and return parsed JSON with resilient behavior."""
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.get(url)
                status = r.status_code
                if r.is_success:
                    try:
                        return {"ok": True, "status": status, "data": r.json(), "error": None}
                    except Exception as parse_err:
                        return {"ok": False, "status": status, "data": None, "error": f"JSON parse error: {parse_err}"}
                # Retry on 5xx server errors
                if 500 <= status < 600 and attempt < retries:
                    time.sleep(0.5 * attempt)
                    continue
                return {"ok": False, "status": status, "data": None, "error": f"HTTP {status}: {r.text[:300]}"}
        except Exception as e:
            last_err = e
            if attempt < retries: # Retry on transient network errors
                time.sleep(0.5 * attempt)
                continue
    return {"ok": False, "status": None, "data": None, "error": str(last_err) if last_err else "Unknown error"}