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

def weather_by_zip(zip_code: str, *, timeout: float = 10.0) -> Dict[str, Any]:
    """Fetch current weather for a US ZIP code using zippopotam.us + Open-Meteo."""
    postal_code = zip_code.strip()
    if len(postal_code) != 5 or not postal_code.isdigit():
        return {
            "ok": False,
            "error": "ZIP codes must be exactly 5 digits (US only).",
            "status": None,
            "data": None,
        }

    try:
        zip_resp = httpx.get(
            f"https://api.zippopotam.us/us/{postal_code}",
            timeout=timeout,
        )
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "data": None,
            "error": f"Failed to look up ZIP metadata: {exc}",
        }

    if zip_resp.status_code != 200:
        return {
            "ok": False,
            "status": zip_resp.status_code,
            "data": None,
            "error": f"ZIP lookup failed ({zip_resp.status_code}).",
        }

    try:
        zip_json = zip_resp.json()
        place = zip_json["places"][0]
        latitude = float(place["latitude"])
        longitude = float(place["longitude"])
        city = place.get("place name", "")
        state = place.get("state abbreviation", "")
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "data": None,
            "error": f"Malformed ZIP response: {exc}",
        }

    try:
        weather_resp = httpx.get(
            (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={latitude:.4f}&longitude={longitude:.4f}"
                "&current_weather=true&temperature_unit=fahrenheit"
                "&wind_speed_unit=mph"
            ),
            timeout=timeout,
        )
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "data": None,
            "error": f"Failed to fetch weather data: {exc}",
        }

    if weather_resp.status_code != 200:
        return {
            "ok": False,
            "status": weather_resp.status_code,
            "data": None,
            "error": f"Weather service error ({weather_resp.status_code}).",
        }

    try:
        weather_json = weather_resp.json()
        current = weather_json.get("current_weather")
        if not current:
            raise ValueError("Missing current_weather field.")
        summary = {
            "location": {
                "zip": postal_code,
                "city": city,
                "state": state,
                "latitude": latitude,
                "longitude": longitude,
            },
            "temperature_f": current.get("temperature"),
            "windspeed_mph": current.get("windspeed"),
            "wind_direction_deg": current.get("winddirection"),
            "weather_code": current.get("weathercode"),
            "observed_at": current.get("time"),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "data": None,
            "error": f"Malformed weather response: {exc}",
        }

    summary_text_parts = [
        f"Current weather for {city}, {state} {postal_code}:",
        f"Temperature {summary['temperature_f']} °F",
    ]
    if summary["windspeed_mph"] is not None:
        summary_text_parts.append(f"Wind {summary['windspeed_mph']} mph")

    summary["summary"] = "; ".join(summary_text_parts)

    return {
        "ok": True,
        "status": 200,
        "data": summary,
        "error": None,
    }
