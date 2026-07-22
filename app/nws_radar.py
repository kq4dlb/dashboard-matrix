from __future__ import annotations

import base64
import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from app.paths import data_dir

RADAR_STATIONS_URL = "https://api.weather.gov/radar/stations"
CACHE_PATH = data_dir() / "nws_radar_stations.json"
CACHE_SECONDS = 24 * 60 * 60
USER_AGENT = "Dashboard-Matrix/NOAA-Radar (kq4dlb@kq4dlb.com)"
FALLBACK_RADAR_URL = "https://radar.weather.gov/"


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    value = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2.0) ** 2
    )
    # Floating-point rounding can place value microscopically outside 0..1.
    value = max(0.0, min(1.0, value))
    return radius_km * 2.0 * math.atan2(math.sqrt(value), math.sqrt(1.0 - value))


def _read_cache(*, allow_stale: bool) -> list[dict[str, Any]]:
    if not CACHE_PATH.exists():
        return []

    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        fetched_at = float(payload.get("fetched_at", 0))
        if not allow_stale and time.time() - fetched_at > CACHE_SECONDS:
            return []
        stations = payload.get("stations", [])
        return stations if isinstance(stations, list) else []
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return []


def _write_cache(stations: list[dict[str, Any]]) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = CACHE_PATH.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {"fetched_at": time.time(), "stations": stations},
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        temporary.replace(CACHE_PATH)
    except OSError:
        # Cache persistence must never prevent a dashboard from loading.
        return


def _parse_station_feature(feature: dict[str, Any]) -> dict[str, Any] | None:
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates") or []
    properties = feature.get("properties") or {}

    station_id = (
        properties.get("stationIdentifier")
        or properties.get("id")
        or str(feature.get("id", "")).rstrip("/").split("/")[-1]
    )
    if not station_id:
        return None

    if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
        return None

    try:
        longitude = float(coordinates[0])
        latitude = float(coordinates[1])
    except (TypeError, ValueError):
        return None

    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None

    return {
        "id": str(station_id).upper(),
        "name": properties.get("name") or str(station_id).upper(),
        "latitude": latitude,
        "longitude": longitude,
    }


def fetch_radar_stations() -> list[dict[str, Any]]:
    cached = _read_cache(allow_stale=False)
    if cached:
        return cached

    request = urllib.request.Request(
        RADAR_STATIONS_URL,
        headers={
            "Accept": "application/geo+json, application/json",
            "User-Agent": USER_AGENT,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read()
        payload = json.loads(raw.decode("utf-8"))
        features = payload.get("features", []) if isinstance(payload, dict) else []
        stations = [
            station
            for feature in features
            if isinstance(feature, dict)
            if (station := _parse_station_feature(feature)) is not None
        ]
        if stations:
            _write_cache(stations)
            return stations
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        OSError,
        TypeError,
        ValueError,
    ):
        pass

    # A stale station list is preferable to making the whole dashboard fail.
    return _read_cache(allow_stale=True)


def nearest_radar_station(
    latitude: float,
    longitude: float,
    stations: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    try:
        candidates = stations if stations is not None else fetch_radar_stations()
        valid = [
            station
            for station in candidates
            if {"id", "latitude", "longitude"}.issubset(station)
        ]
        if not valid:
            return None

        return min(
            valid,
            key=lambda station: _distance_km(
                float(latitude),
                float(longitude),
                float(station["latitude"]),
                float(station["longitude"]),
            ),
        )
    except (TypeError, ValueError, KeyError, OverflowError):
        return None


def build_radar_url(
    latitude: float,
    longitude: float,
    station_id: str | None = None,
    *,
    zoom: float = 8.0,
    layer: str = "sr_bref",
    animate: bool = True,
) -> str:
    normalized_station = (station_id or "").strip().upper() or None
    safe_latitude = max(-90.0, min(90.0, float(latitude)))
    safe_longitude = max(-180.0, min(180.0, float(longitude)))
    safe_zoom = max(3.0, min(float(zoom), 14.0))

    settings = {
        "agenda": {
            "id": "local",
            "center": [round(safe_longitude, 6), round(safe_latitude, 6)],
            "location": None,
            "zoom": safe_zoom,
            "filter": "WSR-88D" if normalized_station else None,
            "layer": layer or "sr_bref",
            "station": normalized_station,
        },
        "animating": bool(animate),
        "base": "standard",
        "artcc": False,
        "county": True,
        "cwa": False,
        "rfc": False,
        "state": False,
        "menu": True,
        "shortFusedOnly": True,
        "opacity": {
            "alerts": 0.8,
            "local": 0.68,
            "localStations": 0.54,
            "national": 0.6,
        },
    }

    encoded = base64.urlsafe_b64encode(
        json.dumps(settings, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"https://radar.weather.gov/?settings=v1_{encoded}"


def resolve_radar_source(source: str, latitude: float, longitude: float) -> str:
    """
    Resolve Dashboard Matrix radar source syntax without ever raising into the dashboard API.

    Examples:
      nws-radar://auto
      nws-radar://KOHX
      nws-radar://mosaic?zoom=7
      nws-radar://auto?zoom=9&animate=false
    """
    if not isinstance(source, str) or not source.lower().startswith("nws-radar://"):
        return source

    try:
        value = source[len("nws-radar://") :]
        target, _, raw_query = value.partition("?")
        target = target.strip().upper() or "AUTO"
        query = parse_qs(raw_query, keep_blank_values=False)

        def first(name: str, default: str) -> str:
            values = query.get(name)
            return values[0] if values else default

        try:
            zoom = float(first("zoom", "8"))
        except ValueError:
            zoom = 8.0

        animate = first("animate", "true").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
        layer = first("layer", "sr_bref").strip() or "sr_bref"

        station_id: str | None
        if target in {"AUTO", "NEAREST"}:
            nearest = nearest_radar_station(float(latitude), float(longitude))
            station_id = str(nearest["id"]) if nearest else None
        elif target in {"MOSAIC", "NATIONAL", "LOCATION"}:
            station_id = None
        else:
            station_id = target

        return build_radar_url(
            float(latitude),
            float(longitude),
            station_id,
            zoom=zoom,
            layer=layer,
            animate=animate,
        )
    except Exception:
        # A special source may fail to resolve, but it must never cause
        # /api/dashboards/{slug} to return HTTP 500.
        return FALLBACK_RADAR_URL
