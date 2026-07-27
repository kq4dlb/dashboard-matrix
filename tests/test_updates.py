from fastapi.testclient import TestClient

from app.database import connection
from app.updates import _version, public_update_status
from app.version import APP_VERSION


def test_release_versions_compare_prerelease_numbers():
    assert _version("v0.1.0-beta.2") > _version("0.1.0-beta")
    assert _version("0.1.0") > _version("0.1.0-beta.9")
    assert _version("0.2.0-beta") > _version("0.1.9")


def test_public_status_is_unknown_before_check(configured_client: TestClient):
    status = configured_client.get("/api/updates/status")
    assert status.status_code == 200
    assert status.headers["cache-control"] == "no-store"
    data = status.json()
    assert data["state"] == "unknown"
    assert data["current_version"] == APP_VERSION
    assert data["update_available"] is False


def test_public_status_reports_available_release(configured_client: TestClient):
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO update_checks(
                id,checked_at,channel,current_version,latest_version,
                update_available,release_url,message,published_at,
                prerelease,error
            ) VALUES(1,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "2026-07-24T12:00:00+00:00",
                "beta",
                APP_VERSION,
                "0.1.0-beta.2",
                1,
                "https://github.com/kq4dlb/dashboard-matrix/releases/tag/v0.1.0-beta.2",
                "Dashboard Matrix 0.1.0-beta.2 is available.",
                "2026-07-24T12:00:00Z",
                1,
                "",
            ),
        )
    data = configured_client.get("/api/updates/status").json()
    assert data["state"] == "available"
    assert data["update_available"] is True
    assert data["latest_version"] == "0.1.0-beta.2"
    assert "error" not in data
    assert public_update_status()["release_url"].endswith("v0.1.0-beta.2")
