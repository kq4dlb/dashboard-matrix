from __future__ import annotations

from html.parser import HTMLParser

from fastapi.testclient import TestClient


class _AdminTabParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tabs: list[dict[str, str]] = []
        self.panels: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs):
        values = {key: value if value is not None else "" for key, value in attrs}
        if values.get("role") == "tab":
            self.tabs.append(values)
        elif values.get("role") == "tabpanel":
            self.panels.append(values)


def test_admin_uses_accessible_tabs(configured_client: TestClient):
    response = configured_client.get("/admin")
    assert response.status_code == 200

    parser = _AdminTabParser()
    parser.feed(response.text)

    assert [tab.get("data-admin-tab") for tab in parser.tabs] == [
        "overview",
        "dashboards",
        "layouts",
        "sources",
        "extensions",
    ]
    assert [panel.get("data-admin-panel") for panel in parser.panels] == [
        "overview",
        "dashboards",
        "layouts",
        "sources",
        "extensions",
    ]
    assert "hidden" not in parser.panels[0]
    assert all("hidden" in panel for panel in parser.panels[1:])

    panel_ids = {panel["id"]: panel for panel in parser.panels}
    for tab in parser.tabs:
        panel = panel_ids[tab["aria-controls"]]
        assert panel["aria-labelledby"] == tab["id"]


def test_admin_tabs_preserve_existing_workflows(configured_client: TestClient):
    page = configured_client.get("/admin").text
    for element_id in (
        "station-form",
        "password-form",
        "dashboard-form",
        "tile-form",
        "layout-transfer-section",
        "updates-section",
        "theme-section",
        "proxy-form",
        "catalog-form",
        "market-source-list",
        "plugin-list",
        "tile-list",
    ):
        assert f'id="{element_id}"' in page

    assert "/static/css/admin-tabs.css" in page
    assert "/static/js/admin-tabs.js" in page
