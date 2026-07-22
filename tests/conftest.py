from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DATA = Path(__file__).resolve().parent / ".test-data"
os.environ["DASHBOARD_MATRIX_DATA_DIR"] = str(TEST_DATA)
os.environ["DASHBOARD_MATRIX_DISABLE_HAMQSL"] = "1"
os.environ["DASHBOARD_MATRIX_DISABLE_UPDATE_CHECKS"] = "1"
os.environ["DASHBOARD_MATRIX_ADMIN_PASSWORD"] = "admin"
os.environ["DASHBOARD_MATRIX_SESSION_SECRET"] = "test-session-secret"


def _reset() -> None:
    shutil.rmtree(TEST_DATA, ignore_errors=True)


@pytest.fixture
def fresh_client():
    from app.main import app

    _reset()
    with TestClient(app) as client:
        yield client
    _reset()


@pytest.fixture
def configured_client(fresh_client: TestClient):
    response = fresh_client.post(
        "/api/setup",
        json={
            "display_name": "Test Matrix",
            "callsign": "KQ4DLB",
            "grid_square": "EM66hb",
            "template": "amateur-radio",
            "password": "testpass123",
            "theme": "matrix-light",
            "release_channel": "beta",
        },
    )
    assert response.status_code == 200, response.text
    return fresh_client


def pytest_sessionfinish(session, exitstatus):
    _reset()
