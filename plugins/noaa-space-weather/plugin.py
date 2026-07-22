from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

USER_AGENT = "Dashboard-Matrix/1.6.2 (+https://github.com/)"
BASE = "https://services.swpc.noaa.gov"

URLS = {
    "kp": f"{BASE}/products/noaa-planetary-k-index.json",
    "kp_forecast": f"{BASE}/products/noaa-planetary-k-index-forecast.json",
    "scales": f"{BASE}/products/noaa-scales.json",
    "mag": f"{BASE}/json/rtsw/rtsw_mag_1m.json",
    "wind": f"{BASE}/json/rtsw/rtsw_wind_1m.json",
    "alerts": f"{BASE}/products/alerts.json",
    "xray": f"{BASE}/json/goes/primary/xrays-6-hour.json",
}


def _get(url: str, timeout: float = 12.0) -> Any:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"NOAA returned HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(f"Unable to reach NOAA SWPC: {reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("NOAA returned data that was not valid JSON") from exc


def _row_objects(data: Any) -> list[dict[str, Any]]:
    """Accept NOAA header-row arrays or newer arrays of JSON objects."""
    if not isinstance(data, list) or not data:
        return []
    if all(isinstance(row, dict) for row in data):
        return [row for row in data if isinstance(row, dict)]
    header = data[0]
    if not isinstance(header, list):
        return []
    rows: list[dict[str, Any]] = []
    for row in data[1:]:
        if isinstance(row, list) and len(row) == len(header):
            rows.append(dict(zip(header, row)))
    return rows


def _latest(data: Any) -> dict[str, Any]:
    rows = _row_objects(data)
    for row in reversed(rows):
        if any(value not in (None, "", "null") for value in row.values()):
            return row
    return {}


def _value(row: dict[str, Any], *names: str, default: Any = "N/A") -> Any:
    lowered = {str(key).lower(): value for key, value in row.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value not in (None, "", "null"):
            return value
    return default


def _number(value: Any) -> float | None:
    try:
        number = float(str(value).strip().split()[0])
        return number if math.isfinite(number) else None
    except (TypeError, ValueError, IndexError):
        return None


def _fmt(value: Any, digits: int = 1, suffix: str = "") -> str:
    number = _number(value)
    if number is None:
        return "N/A"
    text = f"{number:.{digits}f}".rstrip("0").rstrip(".")
    return f"{text}{suffix}"


def _scale(data: Any, letter: str) -> str:
    if isinstance(data, dict):
        current = data.get("0", data)
    elif isinstance(data, list) and data:
        current = data[0] if isinstance(data[0], dict) else {}
    else:
        current = {}
    value = current.get(letter, {}) if isinstance(current, dict) else {}
    if isinstance(value, dict):
        return str(value.get("Scale", value.get("scale", "0")))
    return str(value or "0")


def _kp_status(kp: float | None) -> str:
    if kp is None:
        return "Unknown"
    if kp < 4:
        return "Quiet"
    if kp < 5:
        return "Active"
    return f"G{min(5, max(1, round(kp - 4)))} storm range"


def _xray_class(flux: float | None) -> str:
    if flux is None or flux <= 0:
        return "N/A"
    bands = ((1e-4, "X"), (1e-5, "M"), (1e-6, "C"), (1e-7, "B"), (1e-8, "A"))
    for base, letter in bands:
        if flux >= base:
            return f"{letter}{flux / base:.1f}"
    return f"A{flux / 1e-8:.1f}"


def _metric(label: str, value: Any) -> dict[str, str]:
    return {"label": label, "value": str(value)}


def _message(title: str, error: Exception) -> dict[str, Any]:
    return {"format": "message", "title": title, "message": str(error)}


def _kp_widget() -> dict[str, Any]:
    observed = _latest(_get(URLS["kp"]))
    forecast = _latest(_get(URLS["kp_forecast"]))
    kp_value = _number(_value(observed, "Kp", "kp", "estimated_kp"))
    return {
        "format": "metrics",
        "title": "Planetary Kp",
        "updated": _value(observed, "time_tag", "time", default="N/A"),
        "metrics": [
            _metric("Kp now", _fmt(kp_value)),
            _metric("Condition", _kp_status(kp_value)),
            _metric("Kp forecast", _fmt(_value(forecast, "kp", "Kp", "predicted_kp"))),
            _metric("Forecast time", _value(forecast, "time_tag", "time", default="N/A")),
        ],
    }


def _scales_widget() -> dict[str, Any]:
    scales = _get(URLS["scales"])
    return {
        "format": "metrics",
        "title": "NOAA Storm Scales",
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "metrics": [
            _metric("Radio blackout", f"R{_scale(scales, 'R')}"),
            _metric("Solar radiation", f"S{_scale(scales, 'S')}"),
            _metric("Geomagnetic", f"G{_scale(scales, 'G')}"),
        ],
    }


def _solar_wind_widget() -> dict[str, Any]:
    mag = _latest(_get(URLS["mag"]))
    wind = _latest(_get(URLS["wind"]))
    return {
        "format": "metrics",
        "title": "Real-Time Solar Wind",
        "updated": _value(wind, "time_tag", "time", default=_value(mag, "time_tag", "time", default="N/A")),
        "metrics": [
            _metric("Speed", _fmt(_value(wind, "speed", "bulk_speed"), 0, " km/s")),
            _metric("Density", _fmt(_value(wind, "density", "proton_density"), 1, " p/cm³")),
            _metric("Temperature", _fmt(_value(wind, "temperature"), 0, " K")),
            _metric("Bt", _fmt(_value(mag, "bt", "Bt"), 1, " nT")),
            _metric("Bz GSM", _fmt(_value(mag, "bz_gsm", "bz", "Bz"), 1, " nT")),
        ],
    }


def _xray_widget() -> dict[str, Any]:
    rows = _row_objects(_get(URLS["xray"]))
    preferred = [row for row in rows if str(_value(row, "energy", default="")).lower() in {"0.1-0.8nm", "0.1-0.8 nm"}]
    row = (preferred or rows)[-1] if (preferred or rows) else {}
    flux = _number(_value(row, "flux"))
    return {
        "format": "metrics",
        "title": "GOES X-Ray Flux",
        "updated": _value(row, "time_tag", "time", default="N/A"),
        "metrics": [
            _metric("Flare class", _xray_class(flux)),
            _metric("Flux", f"{flux:.3e} W/m²" if flux is not None else "N/A"),
            _metric("Energy band", _value(row, "energy", default="0.1–0.8 nm")),
            _metric("Satellite", _value(row, "satellite", default="GOES primary")),
        ],
    }


def _alerts_widget(settings: dict[str, Any]) -> dict[str, Any]:
    data = _get(URLS["alerts"])
    alerts = data if isinstance(data, list) else []
    limit = max(1, min(int(settings.get("alert_limit", 5)), 10))
    selected = list(reversed(alerts[-limit:]))
    if not selected:
        return {
            "format": "metrics",
            "title": "SWPC Alerts",
            "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "metrics": [_metric("Status", "No recent alerts")],
        }
    metrics = []
    for index, alert in enumerate(selected, start=1):
        if isinstance(alert, dict):
            product = _value(alert, "product_id", "product", default=f"Alert {index}")
            text = _value(alert, "message", "summary", "description", default="Alert issued")
        else:
            product, text = f"Alert {index}", str(alert)
        compact = " ".join(str(text).split())
        metrics.append(_metric(str(product), compact[:180]))
    return {
        "format": "metrics",
        "title": "SWPC Alerts",
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "metrics": metrics,
    }


def _summary_widget() -> dict[str, Any]:
    observed = _latest(_get(URLS["kp"]))
    scales = _get(URLS["scales"])
    mag = _latest(_get(URLS["mag"]))
    wind = _latest(_get(URLS["wind"]))
    xray_rows = _row_objects(_get(URLS["xray"]))
    preferred = [row for row in xray_rows if str(_value(row, "energy", default="")).lower() in {"0.1-0.8nm", "0.1-0.8 nm"}]
    xray = (preferred or xray_rows)[-1] if (preferred or xray_rows) else {}
    kp = _number(_value(observed, "Kp", "kp", "estimated_kp"))
    return {
        "format": "metrics",
        "title": "NOAA Space Weather Summary",
        "updated": _value(observed, "time_tag", "time", default="N/A"),
        "metrics": [
            _metric("Planetary Kp", _fmt(kp)),
            _metric("Geomagnetic", f"G{_scale(scales, 'G')}"),
            _metric("Radio blackout", f"R{_scale(scales, 'R')}"),
            _metric("Solar radiation", f"S{_scale(scales, 'S')}"),
            _metric("X-ray", _xray_class(_number(_value(xray, "flux")))),
            _metric("Wind", _fmt(_value(wind, "speed", "bulk_speed"), 0, " km/s")),
            _metric("Bz GSM", _fmt(_value(mag, "bz_gsm", "bz", "Bz"), 1, " nT")),
            _metric("Condition", _kp_status(kp)),
        ],
    }


def render(widget_id: str, settings: dict[str, Any], station: dict[str, str]) -> dict[str, Any]:
    del station
    try:
        if widget_id == "space-weather-summary":
            return _summary_widget()
        if widget_id == "kp-index":
            return _kp_widget()
        if widget_id == "storm-scales":
            return _scales_widget()
        if widget_id == "solar-wind":
            return _solar_wind_widget()
        if widget_id == "xray-flux":
            return _xray_widget()
        if widget_id == "swpc-alerts":
            return _alerts_widget(settings)
        raise KeyError(f"Unknown NOAA Space Weather widget: {widget_id}")
    except Exception as exc:
        return _message("NOAA Space Weather", exc)
