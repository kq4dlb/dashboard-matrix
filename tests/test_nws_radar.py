from __future__ import annotations

from app.database import apply_station_placeholders
from app.nws_radar import (
    FALLBACK_RADAR_URL,
    nearest_radar_station,
    resolve_radar_source,
)


def test_nearest_radar_is_selected_from_fixture():
    stations = [
        {"id": "KAAA", "latitude": 36.0, "longitude": -87.0},
        {"id": "KBBB", "latitude": 42.0, "longitude": -93.0},
    ]
    result = nearest_radar_station(36.1, -87.1, stations)
    assert result is not None
    assert result["id"] == "KAAA"


def test_manual_station_does_not_require_network():
    url = resolve_radar_source(
        "nws-radar://KOHX?zoom=9&animate=false",
        36.0625,
        -87.375,
    )
    assert url.startswith("https://radar.weather.gov/?settings=v1_")


def test_mosaic_does_not_require_network():
    url = resolve_radar_source(
        "nws-radar://mosaic?zoom=7",
        36.0625,
        -87.375,
    )
    assert url.startswith("https://radar.weather.gov/?settings=v1_")


def test_bad_coordinates_fall_back_instead_of_raising():
    url = resolve_radar_source("nws-radar://auto", float("nan"), -87.0)
    assert isinstance(url, str)
    assert url.startswith("https://radar.weather.gov/")


def test_dashboard_placeholder_resolver_never_raises(monkeypatch):
    import app.nws_radar

    def explode(*args, **kwargs):
        raise RuntimeError("simulated radar failure")

    monkeypatch.setattr(app.nws_radar, "resolve_radar_source", explode)
    result = apply_station_placeholders(
        "nws-radar://auto",
        {"callsign": "KQ4DLB", "grid_square": "EM66hb"},
    )
    assert result == FALLBACK_RADAR_URL
