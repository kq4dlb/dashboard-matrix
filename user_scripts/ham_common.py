from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

PROJECT_DATA_DIR = Path(os.environ.get("DASHBOARD_MATRIX_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
LOCAL_CACHE_DIR = Path.home() / ".cache" / "dashboard-matrix"
LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
PROJECT_DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_SECONDS = 600
HAMQSL_URL = "https://www.hamqsl.com/solarxml.php"
HAMQSL_SHARED_CACHE = PROJECT_DATA_DIR / "hamqsl_solar.xml"
HAMQSL_STATUS = PROJECT_DATA_DIR / "hamqsl_status.json"
NOAA_KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
NOAA_KP_FORECAST_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
NOAA_SW_MAG_URL = "https://services.swpc.noaa.gov/json/rtsw/rtsw_mag_1m.json"
NOAA_SW_PLASMA_URL = "https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json"
NOAA_ALERTS_URL = "https://services.swpc.noaa.gov/products/alerts.json"

NOAA_SOLAR_CYCLE_URL = "https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json"
NOAA_XRAY_URL = "https://services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json"


def settings() -> dict[str, Any]:
    try:
        value = json.loads(os.environ.get("DASHBOARD_MATRIX_SCRIPT_SETTINGS", "{}"))
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def _diagnostic_error(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}: {exc.reason}"
    if isinstance(exc, urllib.error.URLError):
        return f"Network error: {exc.reason}"
    if isinstance(exc, ssl.SSLError):
        return f"TLS error: {exc}"
    return f"{type(exc).__name__}: {exc}"


def _status_error() -> str:
    if HAMQSL_STATUS.exists():
        try:
            value = json.loads(HAMQSL_STATUS.read_text(encoding="utf-8"))
            return str(value.get("error", "")).strip()
        except Exception:
            pass
    return ""


def fetch_url(url: str, cache_name: str) -> tuple[bytes, bool, bool, str]:
    cache_file = LOCAL_CACHE_DIR / cache_name
    cache_time = LOCAL_CACHE_DIR / f"{cache_name}.time"
    now = int(time.time())
    if cache_file.exists() and cache_time.exists():
        try:
            if now - int(cache_time.read_text().strip()) < CACHE_SECONDS:
                return cache_file.read_bytes(), True, False, ""
        except Exception:
            pass
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Dashboard-Matrix/0.1 (+local dashboard)",
                "Accept": "application/json,application/xml,text/xml;q=0.9,*/*;q=0.8",
            },
        )
        with urllib.request.urlopen(request, timeout=15, context=ssl.create_default_context()) as response:
            data = response.read(2_000_000)
        cache_file.write_bytes(data)
        cache_time.write_text(str(now))
        return data, False, False, ""
    except Exception as exc:
        detail = _diagnostic_error(exc)
        if cache_file.exists():
            return cache_file.read_bytes(), True, True, detail
        return b"", False, True, detail


def xml_text(node: ET.Element, key: str, default: str = "N/A") -> str:
    found = node.find(key)
    return found.text.strip() if found is not None and found.text else default


def load_hamqsl() -> dict[str, Any]:
    # Prefer the central collector's shared last-known-good file.
    raw = b""
    cached = False
    stale = False
    error_detail = ""
    if HAMQSL_SHARED_CACHE.exists():
        try:
            raw = HAMQSL_SHARED_CACHE.read_bytes()
            cached = True
            age = max(0, int(time.time() - HAMQSL_SHARED_CACHE.stat().st_mtime))
            stale = age > CACHE_SECONDS * 2
        except Exception as exc:
            error_detail = _diagnostic_error(exc)

    # If there is no shared cache yet, make one direct attempt so first-run tiles work.
    if not raw:
        raw, cached, stale, error_detail = fetch_url(HAMQSL_URL, "hamqsl_solar.xml")

    if not raw:
        return {
            "error": True,
            "cached": cached,
            "stale": stale,
            "error_detail": error_detail or _status_error() or "No shared or local HamQSL cache is available.",
        }
    try:
        root = ET.fromstring(raw)
        data = root.find(".//solardata")
    except Exception as exc:
        data = None
        error_detail = f"XML parse error: {exc}"
    if data is None:
        return {
            "error": True,
            "cached": cached,
            "stale": True,
            "error_detail": error_detail or "The HamQSL response did not contain a solardata element.",
        }
    bands = [
        {
            "name": band.attrib.get("name", "Band"),
            "time": band.attrib.get("time", ""),
            "condition": (band.text or "N/A").strip(),
        }
        for band in data.findall(".//band")
    ]
    keys = [
        "updated", "solarflux", "sunspots", "aindex", "kindex", "xray",
        "protonflux", "electronflux", "solarwind", "magneticfield",
        "geomagfield", "signalnoise", "muf", "fof2", "aurora", "latdegree",
    ]
    result = {key: xml_text(data, key) for key in keys}
    result.update({
        "error": False,
        "cached": cached,
        "stale": stale,
        "error_detail": error_detail or _status_error(),
        "bands": bands,
    })
    return result


def latest_json_row(url: str, cache_name: str) -> tuple[dict[str, Any] | None, bool, bool]:
    raw, cached, stale, _ = fetch_url(url, cache_name)
    if not raw:
        return None, cached, stale
    try:
        data = json.loads(raw)
    except Exception:
        return None, cached, True
    if not isinstance(data, list) or not data:
        return None, cached, True
    if isinstance(data[-1], dict):
        return data[-1], cached, stale
    if len(data) > 1 and isinstance(data[0], list):
        header = data[0]
        for row in reversed(data[1:]):
            if isinstance(row, list) and len(row) == len(header):
                return dict(zip(header, row)), cached, stale
    return None, cached, True


def load_noaa() -> dict[str, Any]:
    kp, a, b = latest_json_row(NOAA_KP_URL, "noaa_kp.json")
    forecast, c, d = latest_json_row(NOAA_KP_FORECAST_URL, "noaa_kp_forecast.json")
    mag, e, f = latest_json_row(NOAA_SW_MAG_URL, "noaa_mag.json")
    plasma, g, h = latest_json_row(NOAA_SW_PLASMA_URL, "noaa_plasma.json")
    raw, i, j, _ = fetch_url(NOAA_ALERTS_URL, "noaa_alerts.json")
    alerts: list[Any] = []
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                alerts = parsed[-5:]
        except Exception:
            pass
    return {
        "kp": kp,
        "kp_forecast": forecast,
        "mag": mag,
        "plasma": plasma,
        "alerts": alerts,
        "cached": any((a, c, e, g, i)),
        "stale": any((b, d, f, h, j)),
    }


def val(row: dict[str, Any] | None, *keys: str, default: Any = "N/A") -> Any:
    if not row:
        return default
    lowered = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value not in (None, "", "null"):
            return value
    return default


def _latest_object(url: str, cache_name: str) -> tuple[dict[str, Any] | None, bool, bool, str]:
    raw, cached, stale, error = fetch_url(url, cache_name)
    if not raw:
        return None, cached, stale, error
    try:
        data = json.loads(raw)
    except Exception as exc:
        return None, cached, True, f"JSON parse error: {exc}"
    if isinstance(data, list):
        for item in reversed(data):
            if isinstance(item, dict):
                return item, cached, stale, error
    if isinstance(data, dict):
        return data, cached, stale, error
    return None, cached, True, "NOAA response did not contain an object."


def _latest_xray() -> tuple[dict[str, Any] | None, bool, bool, str]:
    raw, cached, stale, error = fetch_url(NOAA_XRAY_URL, "noaa_xray_6h.json")
    if not raw:
        return None, cached, stale, error
    try:
        data = json.loads(raw)
    except Exception as exc:
        return None, cached, True, f"JSON parse error: {exc}"
    if not isinstance(data, list):
        return None, cached, True, "NOAA X-ray response was not a list."
    preferred = [x for x in data if isinstance(x, dict) and str(x.get("energy", "")) == "0.1-0.8nm"]
    rows = preferred or [x for x in data if isinstance(x, dict)]
    return (rows[-1] if rows else None), cached, stale, error


def _flare_class(flux: Any) -> str:
    try:
        value = float(flux)
    except Exception:
        return "N/A"
    classes = ((1e-4, "X"), (1e-5, "M"), (1e-6, "C"), (1e-7, "B"), (1e-8, "A"))
    for base, letter in classes:
        if value >= base:
            return f"{letter}{value / base:.1f}"
    return f"A{value / 1e-8:.1f}" if value > 0 else "A0.0"


def load_noaa_propagation() -> dict[str, Any]:
    solar, solar_cached, solar_stale, solar_error = _latest_object(
        NOAA_SOLAR_CYCLE_URL, "noaa_observed_solar_cycle.json"
    )
    kp, kp_cached, kp_stale = latest_json_row(NOAA_KP_URL, "noaa_kp.json")
    xray, xray_cached, xray_stale, xray_error = _latest_xray()
    if not solar and not kp and not xray:
        return {
            "error": True,
            "error_detail": solar_error or xray_error or "NOAA propagation products are unavailable.",
        }
    sfi = val(solar, "f10.7", "observed_f10.7", "flux", default="N/A")
    sunspots = val(solar, "ssn", "observed_swpc_ssn", "sunspot_number", default="N/A")
    kp_value = val(kp, "kp", "estimated_kp", "Kp", default="N/A")
    updated = val(kp, "time_tag", "time", default=val(solar, "time-tag", "time_tag", default="N/A"))
    try:
        kpf = float(kp_value)
        a_index = round(2.0 ** (kpf + 1.0)) if kpf >= 0 else "N/A"
    except Exception:
        a_index = "N/A"
    geomag = "Quiet"
    try:
        kpf = float(kp_value)
        geomag = "Severe storm" if kpf >= 8 else "Storm" if kpf >= 5 else "Active" if kpf >= 4 else "Unsettled" if kpf >= 3 else "Quiet"
    except Exception:
        pass
    return {
        "error": False,
        "source": "NOAA SWPC fallback",
        "estimated": True,
        "cached": any((solar_cached, kp_cached, xray_cached)),
        "stale": any((solar_stale, kp_stale, xray_stale)),
        "updated": updated,
        "solarflux": sfi,
        "sunspots": sunspots,
        "aindex": a_index,
        "kindex": kp_value,
        "xray": _flare_class(val(xray, "flux", default=0)),
        "muf": "Not supplied by NOAA",
        "fof2": "Not supplied by NOAA",
        "geomagfield": geomag,
        "signalnoise": "Estimated from Kp",
        "error_detail": solar_error or xray_error,
    }


def load_propagation_with_fallback() -> dict[str, Any]:
    ham = load_hamqsl()
    if not ham.get("error"):
        ham["source"] = "HamQSL"
        ham["estimated"] = False
        return ham
    fallback = load_noaa_propagation()
    fallback["hamqsl_error"] = ham.get("error_detail", "HamQSL unavailable")
    return fallback


def estimate_hf_bands(sfi_value: Any, kp_value: Any) -> dict[str, list[dict[str, str]]]:
    try:
        sfi = float(sfi_value)
    except Exception:
        sfi = 80.0
    try:
        kp = float(kp_value)
    except Exception:
        kp = 3.0

    def condition(low: float, good: float, excellent: float, kp_limit: float = 4.0) -> str:
        if kp >= 6:
            return "Poor"
        if kp > kp_limit:
            return "Fair" if sfi >= good else "Poor"
        if sfi >= excellent and kp <= 2:
            return "Excellent"
        if sfi >= good:
            return "Good"
        if sfi >= low:
            return "Fair"
        return "Poor"

    day = [
        {"name": "80m-40m", "time": "day", "condition": "Fair" if kp < 5 else "Poor"},
        {"name": "30m-20m", "time": "day", "condition": condition(65, 85, 140)},
        {"name": "17m-15m", "time": "day", "condition": condition(85, 110, 155, 3.5)},
        {"name": "12m-10m", "time": "day", "condition": condition(100, 140, 180, 3.0)},
    ]
    night = [
        {"name": "80m-40m", "time": "night", "condition": "Good" if kp <= 3 else "Fair" if kp <= 5 else "Poor"},
        {"name": "30m-20m", "time": "night", "condition": condition(60, 80, 130)},
        {"name": "17m-15m", "time": "night", "condition": condition(105, 140, 185, 3.0)},
        {"name": "12m-10m", "time": "night", "condition": condition(140, 180, 220, 2.5)},
    ]
    return {"day": day, "night": night}
