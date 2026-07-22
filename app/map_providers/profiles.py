from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_admin
from app.database import connection, get_station_settings, maidenhead_center, set_setting
from app.websocket import manager

router = APIRouter(tags=["map-profiles"])

MAP_PROFILE_KEY = "map_profile"
MAP_ZOOM_KEY = "map_zoom"
MAP_RADIUS_KEY = "map_radius_miles"
MAP_CUSTOM_LAT_KEY = "map_custom_latitude"
MAP_CUSTOM_LON_KEY = "map_custom_longitude"

PRESETS: dict[str, dict[str, Any]] = {
    "world": {"name": "Worldwide", "center_lat": 20.0, "center_lon": 0.0, "zoom": 2.2, "bounds": [[-60.0, -180.0], [80.0, 180.0]]},
    "north-america": {"name": "North America", "center_lat": 44.0, "center_lon": -103.0, "zoom": 3.5, "bounds": [[7.0, -168.0], [84.0, -52.0]]},
    "continental-us": {"name": "Continental United States", "center_lat": 39.8283, "center_lon": -98.5795, "zoom": 4.6, "bounds": [[24.3963, -124.8489], [49.3844, -66.8854]]},
    "eastern-us": {"name": "Eastern United States", "center_lat": 38.5, "center_lon": -80.5, "zoom": 5.1, "bounds": [[24.0, -92.0], [49.5, -66.0]]},
    "central-us": {"name": "Central United States", "center_lat": 38.5, "center_lon": -97.0, "zoom": 5.0, "bounds": [[25.0, -108.0], [49.5, -86.0]]},
    "western-us": {"name": "Western United States", "center_lat": 39.0, "center_lon": -113.0, "zoom": 4.8, "bounds": [[25.0, -125.0], [49.5, -101.0]]},
    "southeast-us": {"name": "Southeast United States", "center_lat": 33.0, "center_lon": -84.5, "zoom": 5.5, "bounds": [[24.0, -94.0], [39.5, -74.0]]},
    "northeast-us": {"name": "Northeast United States", "center_lat": 42.0, "center_lon": -74.5, "zoom": 5.6, "bounds": [[37.0, -83.0], [48.0, -66.0]]},
    "southwest-us": {"name": "Southwest United States", "center_lat": 34.0, "center_lon": -111.0, "zoom": 5.3, "bounds": [[25.0, -121.0], [39.5, -101.0]]},
    "pacific-northwest": {"name": "Pacific Northwest", "center_lat": 46.0, "center_lon": -120.0, "zoom": 5.5, "bounds": [[41.0, -130.0], [50.5, -110.0]]},
    "local": {"name": "Local station area", "center_lat": None, "center_lon": None, "zoom": 7.0, "bounds": None},
    "custom": {"name": "Custom center", "center_lat": None, "center_lon": None, "zoom": 6.0, "bounds": None},
}


class MapProfileUpdate(BaseModel):
    profile: str = Field(default="continental-us")
    zoom: float | None = Field(default=None, ge=1.0, le=18.0)
    radius_miles: int = Field(default=250, ge=5, le=3000)
    custom_latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    custom_longitude: float | None = Field(default=None, ge=-180.0, le=180.0)


def profile_payload(override: str | None = None) -> dict[str, Any]:
    with connection() as conn:
        settings = get_station_settings(conn)
    profile_id = override or settings.get(MAP_PROFILE_KEY, "continental-us")
    if profile_id not in PRESETS:
        profile_id = "continental-us"
    preset = PRESETS[profile_id]
    station_grid = settings.get("grid_square", "AA00aa")
    station_lat, station_lon = maidenhead_center(station_grid)
    if profile_id == "local":
        center_lat, center_lon = station_lat, station_lon
    elif profile_id == "custom":
        try:
            center_lat = float(settings.get(MAP_CUSTOM_LAT_KEY, station_lat))
            center_lon = float(settings.get(MAP_CUSTOM_LON_KEY, station_lon))
        except (TypeError, ValueError):
            center_lat, center_lon = station_lat, station_lon
    else:
        center_lat = float(preset["center_lat"])
        center_lon = float(preset["center_lon"])
    try:
        zoom = float(settings.get(MAP_ZOOM_KEY, preset["zoom"]))
    except (TypeError, ValueError):
        zoom = float(preset["zoom"])
    try:
        radius = int(settings.get(MAP_RADIUS_KEY, 250))
    except (TypeError, ValueError):
        radius = 250
    return {
        "profile": profile_id,
        "name": preset["name"],
        "center_lat": center_lat,
        "center_lon": center_lon,
        "zoom": max(1.0, min(zoom, 18.0)),
        "radius_miles": max(5, min(radius, 3000)),
        "bounds": preset.get("bounds"),
        "station_lat": station_lat,
        "station_lon": station_lon,
        "grid_square": station_grid,
        "presets": [
            {"id": key, "name": value["name"], "default_zoom": value["zoom"]}
            for key, value in PRESETS.items()
        ],
    }


@router.get("/api/settings/map-profile")
def read_map_profile() -> dict[str, Any]:
    return profile_payload()


@router.put("/api/settings/map-profile")
async def update_map_profile(item: MapProfileUpdate, _: None = Depends(require_admin)) -> dict[str, Any]:
    if item.profile not in PRESETS:
        raise HTTPException(400, "Unknown map profile")
    with connection() as conn:
        set_setting(conn, MAP_PROFILE_KEY, item.profile)
        set_setting(conn, MAP_RADIUS_KEY, str(item.radius_miles))
        if item.zoom is not None:
            set_setting(conn, MAP_ZOOM_KEY, str(item.zoom))
        if item.custom_latitude is not None:
            set_setting(conn, MAP_CUSTOM_LAT_KEY, str(item.custom_latitude))
        if item.custom_longitude is not None:
            set_setting(conn, MAP_CUSTOM_LON_KEY, str(item.custom_longitude))
    await manager.broadcast({"event": "configuration_changed"})
    return profile_payload()
