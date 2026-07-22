from fastapi.testclient import TestClient


def current_layout(client: TestClient) -> dict:
    response = client.get("/api/layout-exports/current")
    assert response.status_code == 200
    return response.json()


def test_analyze_and_rename_conflict(configured_client: TestClient):
    document = current_layout(configured_client)
    analysis = configured_client.post(
        "/api/layout-imports/analyze",
        json={"document": document},
    )
    assert analysis.status_code == 200
    assert any(item["slug"] == "main" for item in analysis.json()["conflicts"])

    imported = configured_client.post(
        "/api/layout-imports",
        json={
            "document": document,
            "conflict_strategy": "rename",
            "include_station": False,
            "source_name": "round-trip.json",
        },
    )
    assert imported.status_code == 200
    assert imported.json()["renamed"]
    slugs = {item["slug"] for item in configured_client.get("/api/dashboards").json()}
    assert "main-2" in slugs


def test_merge_places_cards_below_existing(configured_client: TestClient):
    document = current_layout(configured_client)
    before = configured_client.get("/api/dashboards/main").json()["tiles"]
    merged = configured_client.post(
        "/api/layout-imports",
        json={"document": document, "conflict_strategy": "merge"},
    )
    assert merged.status_code == 200
    after = configured_client.get("/api/dashboards/main").json()["tiles"]
    assert len(after) > len(before)
    original_bottom = max(tile["row_pos"] + tile["height"] - 1 for tile in before)
    new_tiles = [tile for tile in after if tile["id"] not in {item["id"] for item in before}]
    assert min(tile["row_pos"] for tile in new_tiles) > original_bottom
