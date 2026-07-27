from __future__ import annotations

from fastapi.testclient import TestClient


def test_admin_tab_assets_are_served(configured_client: TestClient):
    page = configured_client.get("/admin")
    assert page.status_code == 200
    assert "/static/js/admin-tabs.js" in page.text
    assert "/static/css/admin-tabs.css" in page.text
    assert configured_client.get("/static/js/admin-tabs.js").status_code == 200
    assert configured_client.get("/static/css/admin-tabs.css").status_code == 200


def test_saved_station_identity_is_returned_and_rendered(configured_client: TestClient):
    response = configured_client.put(
        "/api/settings/station",
        json={"callsign": "KQ4DLB", "grid_square": "EM66hb"},
    )
    assert response.status_code == 200
    station = response.json()
    assert station["callsign"] == "KQ4DLB"
    assert station["grid_square"] == "EM66hb"
    assert isinstance(station["latitude"], float)
    assert isinstance(station["longitude"], float)

    dashboard = configured_client.get("/")
    assert dashboard.status_code == 200
    for element_id in (
        "station-callsign",
        "station-grid",
        "station-latitude",
        "station-longitude",
    ):
        assert f'id="{element_id}"' in dashboard.text

    admin = configured_client.get("/admin")
    for element_id in (
        "station-summary-callsign",
        "station-summary-grid",
        "station-summary-latitude",
        "station-summary-longitude",
    ):
        assert f'id="{element_id}"' in admin.text


def test_dashboard_uses_server_light_theme_default(configured_client: TestClient):
    response = configured_client.get("/")
    assert response.status_code == 200
    assert 'data-default-theme="matrix-light"' in response.text
    dashboard_js = configured_client.get("/static/js/dashboard.js").text
    assert 'document.body.dataset.defaultTheme||"matrix-light"' in dashboard_js
    assert 'serverDefaultTheme="matrix-dark"' not in dashboard_js
