from fastapi.testclient import TestClient

from app.database import maidenhead_center


def login(client: TestClient, password: str = "testpass123") -> None:
    response = client.post(
        "/admin/login",
        data={"password": password},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_first_run_wizard_and_templates(fresh_client: TestClient):
    assert fresh_client.get("/", follow_redirects=False).status_code == 303
    page = fresh_client.get("/setup")
    assert page.status_code == 200
    assert "First-run setup" in page.text
    status = fresh_client.get("/api/setup/status").json()
    assert status["complete"] is False
    assert {item["id"] for item in status["templates"]} == {
        "blank",
        "amateur-radio",
        "home-lab",
    }


def test_dashboard_and_admin_after_setup(configured_client: TestClient):
    root = configured_client.get("/")
    assert root.status_code == 200
    assert "dashboard-grid" in root.text
    assert "Dashboard Matrix" in root.text
    assert configured_client.get("/setup", follow_redirects=False).status_code == 303
    page = configured_client.get("/admin")
    assert page.status_code == 200
    assert "Layout import, export, and Exchange publishing" in page.text
    assert "{{CALLSIGN}}" in page.text


def test_health(fresh_client: TestClient):
    data = fresh_client.get("/health").json()
    assert data["status"] == "ok"
    assert data["product"] == "dashboard-matrix"
    assert data["version"] == "0.1.0-beta"


def test_maidenhead_center():
    lat, lon = maidenhead_center("EM66hb")
    assert 36.0 < lat < 36.2
    assert -87.5 < lon < -87.2


def test_station_settings_and_substitution(configured_client: TestClient):
    updated = configured_client.put(
        "/api/settings/station",
        json={"callsign": "kq4dlb", "grid_square": "EM66hb"},
    )
    assert updated.status_code == 200
    assert updated.json()["default_theme"] == "matrix-light"
    dashboard = configured_client.get("/api/dashboards/main").json()
    sources = [
        source
        for card in dashboard["tiles"]
        for source in card["sources"]
        if "pskreporter.info" in source
    ]
    assert sources and "callsign=KQ4DLB" in sources[0]


def test_catalog_plugins_themes_and_layout_export(configured_client: TestClient):
    catalog = configured_client.get("/api/catalog").json()
    assert any(item["item_id"] == "psk-reporter" for item in catalog)
    assert any(item["item_id"] == "noaa-radar-location-mosaic" for item in catalog)
    plugins = configured_client.get("/api/plugins")
    assert plugins.status_code == 200
    aprs = next(item for item in plugins.json() if item["id"] == "aprs")
    assert set(aprs["permissions"]) == {"network", "secrets"}
    assert "api_key" in aprs["secret_status"]
    themes = configured_client.get("/api/themes").json()
    assert {item["id"] for item in themes} >= {"matrix-dark", "matrix-light"}
    exported = configured_client.get("/api/layout-exports/download")
    assert exported.status_code == 200
    assert exported.json()["export_type"] == "dashboard-matrix-layout"
