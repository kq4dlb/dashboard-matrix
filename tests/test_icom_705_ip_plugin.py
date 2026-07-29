from __future__ import annotations

import importlib.util
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace


class FakeLanBackendConfig:
    def __init__(self, **values):
        self.values = values


class FakeRadio:
    connected = True
    radio_ready = True
    model = "IC-705"
    backend_id = "rigplane"

    def __init__(self):
        self.radio_state = SimpleNamespace(
            ptt=False,
            split=False,
            power_level=128,
            power_meter=64,
            swr_meter=12,
            alc_meter=5,
            vd_meter=200,
            id_meter=20,
            mic_gain=100,
            main=SimpleNamespace(
                active_slot="A",
                s_meter=120,
                af_level=80,
                rf_gain=200,
                squelch=20,
                data_mode=1,
            ),
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.connected = False

    async def get_freq(self, receiver=0):
        return 14_074_000

    async def get_mode(self, receiver=0):
        return "USB", 2

    async def get_data_mode(self):
        return True

    async def get_s_meter(self, receiver=0):
        return 120

    async def get_swr(self):
        return 1.2

    async def get_rf_power(self):
        return 128

    async def get_power_meter(self):
        return 64

    async def get_swr_meter(self):
        return 12

    async def get_alc_meter(self):
        return 5

    async def get_vd_meter(self):
        return 200

    async def get_id_meter(self):
        return 20

    async def get_af_level(self, receiver=0):
        return 80

    async def get_rf_gain(self, receiver=0):
        return 200

    async def get_squelch(self, receiver=0):
        return 20

    async def get_mic_gain(self):
        return 100


def _load_plugin(monkeypatch, *, env_password: str | None = "radio-password"):
    calls = {"create": 0}

    def create_radio(config):
        calls["create"] += 1
        return FakeRadio()

    fake_rigplane = types.ModuleType("rigplane")
    fake_rigplane.LanBackendConfig = FakeLanBackendConfig
    fake_rigplane.create_radio = create_radio
    monkeypatch.setitem(sys.modules, "rigplane", fake_rigplane)
    if env_password is None:
        monkeypatch.delenv("DASHBOARD_MATRIX_SECRET_PASSWORD", raising=False)
    else:
        monkeypatch.setenv("DASHBOARD_MATRIX_SECRET_PASSWORD", env_password)

    plugin_path = (
        Path(__file__).resolve().parents[1]
        / "plugins"
        / "icom-705-ip"
        / "plugin.py"
    )
    spec = importlib.util.spec_from_file_location("test_icom_705_ip_plugin_module", plugin_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, calls


def test_cards_share_one_background_radio_connection(monkeypatch):
    plugin, calls = _load_plugin(monkeypatch)
    settings = {
        "host": "192.0.2.70",
        "username": "dashboard",
        "poll_interval": 0.5,
        "command_timeout": 1,
    }

    plugin.render("radio-compact", settings, {"CALLSIGN": "KQ4DLB"})
    deadline = time.time() + 3
    status = {}
    while time.time() < deadline:
        status = plugin.render("radio-status", settings, {"CALLSIGN": "KQ4DLB"})
        metrics = {item["label"]: item["value"] for item in status.get("metrics", [])}
        if metrics.get("Frequency") == "14.074000 MHz":
            break
        time.sleep(0.05)

    health = plugin.render("connection-health", settings, {})
    status_metrics = {item["label"]: item["value"] for item in status["metrics"]}
    health_metrics = {item["label"]: item["value"] for item in health["metrics"]}

    assert status_metrics["Frequency"] == "14.074000 MHz"
    assert status_metrics["Mode"] == "USB-D"
    assert health_metrics["Connection"] == "Connected"
    assert calls["create"] == 1
    plugin.shutdown()


def test_admin_password_works_without_environment_secret(monkeypatch):
    plugin, _ = _load_plugin(monkeypatch, env_password=None)
    config = plugin.RadioConfig.from_settings(
        {
            "host": "192.0.2.70",
            "username": "dashboard",
            "password": "admin-stored-password",
        }
    )
    assert config.password == "admin-stored-password"
    plugin.shutdown()


def test_environment_secret_remains_supported(monkeypatch):
    plugin, _ = _load_plugin(monkeypatch, env_password="environment-password")
    config = plugin.RadioConfig.from_settings(
        {
            "host": "192.0.2.70",
            "username": "dashboard",
            "password": "",
        }
    )
    assert config.password == "environment-password"
    plugin.shutdown()
