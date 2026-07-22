from __future__ import annotations

import time
from typing import Any
import httpx

USER_AGENT = "Dashboard-Matrix/0.1 (local amateur-radio dashboard)"
_cache: dict[str, tuple[float, dict[str, Any]]] = {}

async def _json(url: str, ttl: int = 240) -> dict[str, Any] | list[Any]:
    cached = _cache.get(url)
    if cached and time.time() - cached[0] < ttl:
        return cached[1]
    async with httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json, application/json"}) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
    _cache[url] = (time.time(), data)
    return data

async def nws_forecast(settings: dict[str, Any]) -> dict[str, Any]:
    lat = float(settings.get("latitude", 36.077))
    lon = float(settings.get("longitude", -87.387))
    periods = max(1, min(int(settings.get("periods", 4)), 8))
    point = await _json(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}", 86400)
    forecast_url = point["properties"]["forecast"]
    forecast = await _json(forecast_url, 300)
    selected = forecast["properties"]["periods"][:periods]
    return {
        "provider": "nws_forecast",
        "location": point["properties"].get("relativeLocation", {}).get("properties", {}).get("city", "Configured location"),
        "periods": [{"name": p["name"], "temperature": p["temperature"], "unit": p["temperatureUnit"], "wind": f"{p['windSpeed']} {p['windDirection']}", "summary": p["shortForecast"], "icon": p.get("icon")} for p in selected],
        "updated": forecast["properties"].get("updated")
    }

async def swpc_scales(_: dict[str, Any]) -> dict[str, Any]:
    data = await _json("https://services.swpc.noaa.gov/products/noaa-scales.json", 240)
    current = data.get("0", {}) if isinstance(data, dict) else {}
    return {"provider":"swpc_scales", "scales": {k: current.get(k, {}).get("Scale", "0") for k in ("R", "S", "G")}, "raw": current}

async def swpc_k_index(_: dict[str, Any]) -> dict[str, Any]:
    data = await _json("https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json", 240)
    rows = data[1:] if isinstance(data, list) else []
    latest = rows[-1] if rows else []
    recent = rows[-12:]
    return {"provider":"swpc_k_index", "time_tag": latest[0] if latest else None, "kp": float(latest[1]) if len(latest) > 1 else None, "estimated": latest[2] if len(latest) > 2 else None, "history": [{"time": r[0], "kp": float(r[1])} for r in recent if len(r) > 1]}

PROVIDERS = {"nws_forecast": nws_forecast, "swpc_scales": swpc_scales, "swpc_k_index": swpc_k_index}

async def fetch_provider(name: str, settings: dict[str, Any]) -> dict[str, Any]:
    provider = PROVIDERS.get(name)
    if provider is None:
        raise KeyError(f"Unknown provider: {name}")
    return await provider(settings)
