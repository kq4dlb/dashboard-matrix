from __future__ import annotations

import asyncio
import hashlib
import os
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any

try:
    from rigplane import LanBackendConfig, create_radio
except Exception as exc:  # Import errors can include missing native audio libraries.
    LanBackendConfig = None  # type: ignore[assignment]
    create_radio = None  # type: ignore[assignment]
    _RIGPLANE_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
else:
    _RIGPLANE_IMPORT_ERROR = ""


@dataclass(frozen=True, slots=True)
class RadioConfig:
    host: str
    username: str
    password: str
    control_port: int
    radio_address: int
    poll_interval: float
    command_timeout: float
    reconnect_delay: float
    stale_after: float
    max_watts: float

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> "RadioConfig":
        address_text = str(settings.get("radio_address", "0xA4")).strip()
        try:
            radio_address = int(address_text, 0)
        except ValueError as exc:
            raise ValueError("CI-V address must look like 0xA4 or 164") from exc
        if not 0 <= radio_address <= 0xFF:
            raise ValueError("CI-V address must be between 0x00 and 0xFF")

        host = str(settings.get("host", "ic-705.local")).strip()
        username = str(settings.get("username", "")).strip()
        password = os.getenv("DASHBOARD_MATRIX_SECRET_PASSWORD", "")
        if not host:
            raise ValueError("Radio IP or hostname is required")
        if not username:
            raise ValueError("Remote username is required")
        if not password:
            raise ValueError("Remote password is unavailable. In Admin, map password to ICOM_705_REMOTE_PASSWORD or file:/absolute/path/to/password.")

        return cls(
            host=host,
            username=username,
            password=password,
            control_port=_bounded_int(settings.get("control_port", 50001), 1, 65535),
            radio_address=radio_address,
            poll_interval=_bounded_float(settings.get("poll_interval", 1.5), 0.5, 30.0),
            command_timeout=_bounded_float(settings.get("command_timeout", 2.0), 0.5, 15.0),
            reconnect_delay=_bounded_float(settings.get("reconnect_delay", 3.0), 1.0, 60.0),
            stale_after=_bounded_float(settings.get("stale_after", 8.0), 2.0, 120.0),
            max_watts=_bounded_float(settings.get("max_watts", 10.0), 1.0, 20.0),
        )

    def fingerprint(self) -> str:
        password_hash = hashlib.sha256(self.password.encode("utf-8")).hexdigest()
        values = (
            self.host,
            self.username,
            password_hash,
            self.control_port,
            self.radio_address,
            self.poll_interval,
            self.command_timeout,
            self.reconnect_delay,
            self.stale_after,
            self.max_watts,
        )
        return hashlib.sha256(repr(values).encode("utf-8")).hexdigest()


def _bounded_float(value: Any, low: float, high: float) -> float:
    number = float(value)
    return max(low, min(high, number))


def _bounded_int(value: Any, low: int, high: int) -> int:
    number = int(value)
    return max(low, min(high, number))


class SharedRadioPoller:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._config_fingerprint = ""
        self._config: RadioConfig | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._snapshot: dict[str, Any] = self._empty_snapshot()

    @staticmethod
    def _empty_snapshot() -> dict[str, Any]:
        return {
            "state": "idle",
            "connected": False,
            "radio_ready": False,
            "model": "IC-705",
            "backend": "rigplane-lan",
            "updated_epoch": 0.0,
            "connected_epoch": 0.0,
            "poll_latency_ms": None,
            "error": "",
            "frequency_hz": None,
            "mode": "Unknown",
            "filter_num": None,
            "data_mode": False,
            "active_vfo": "A",
            "ptt": False,
            "split": False,
            "power_level": None,
            "s_meter": None,
            "swr": None,
            "power_meter": None,
            "swr_meter": None,
            "alc_meter": None,
            "vd_meter": None,
            "id_meter": None,
            "af_level": None,
            "rf_gain": None,
            "squelch": None,
            "mic_gain": None,
        }

    def ensure_started(self, config: RadioConfig) -> None:
        fingerprint = config.fingerprint()
        old_thread: threading.Thread | None = None
        with self._lock:
            if (
                fingerprint == self._config_fingerprint
                and self._thread is not None
                and self._thread.is_alive()
            ):
                return
            if self._thread is not None and self._thread.is_alive():
                self._stop_event.set()
                old_thread = self._thread

        if old_thread is not None:
            old_thread.join(timeout=3.0)
            if old_thread.is_alive():
                self._update(
                    state="restarting",
                    connected=False,
                    radio_ready=False,
                    error="Waiting for the previous radio connection to close",
                )
                return

        with self._lock:
            self._config = config
            self._config_fingerprint = fingerprint
            self._stop_event = threading.Event()
            self._snapshot = self._empty_snapshot() | {
                "state": "starting",
                "error": "",
            }
            self._thread = threading.Thread(
                target=self._thread_main,
                args=(config, self._stop_event),
                name="icom-705-ip-poller",
                daemon=True,
            )
            self._thread.start()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._snapshot)

    def stop(self) -> None:
        with self._lock:
            thread = self._thread
            self._stop_event.set()
        if thread is not None and thread.is_alive():
            thread.join(timeout=4.0)

    def _thread_main(self, config: RadioConfig, stop_event: threading.Event) -> None:
        try:
            asyncio.run(self._run(config, stop_event))
        except Exception as exc:
            self._update(
                state="error",
                connected=False,
                radio_ready=False,
                error=f"{type(exc).__name__}: {exc}",
            )

    async def _run(self, config: RadioConfig, stop_event: threading.Event) -> None:
        assert LanBackendConfig is not None
        assert create_radio is not None

        while not stop_event.is_set():
            self._update(state="connecting", connected=False, radio_ready=False, error="")
            try:
                backend_config = LanBackendConfig(
                    host=config.host,
                    port=config.control_port,
                    username=config.username,
                    password=config.password,
                    radio_addr=config.radio_address,
                    timeout=config.command_timeout,
                    auto_reconnect=True,
                    reconnect_delay=config.reconnect_delay,
                    model="IC-705",
                )
                async with create_radio(backend_config) as radio:
                    self._update(
                        state="connected",
                        connected=True,
                        radio_ready=bool(getattr(radio, "radio_ready", True)),
                        model=str(getattr(radio, "model", "IC-705") or "IC-705"),
                        backend=str(getattr(radio, "backend_id", "rigplane-lan")),
                        connected_epoch=time.time(),
                        error="",
                    )
                    while not stop_event.is_set() and bool(getattr(radio, "connected", True)):
                        await self._poll_once(radio, config)
                        await _sleep_interruptibly(stop_event, config.poll_interval)
            except Exception as exc:
                self._update(
                    state="error",
                    connected=False,
                    radio_ready=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
                await _sleep_interruptibly(stop_event, config.reconnect_delay)

        self._update(state="stopped", connected=False, radio_ready=False)

    async def _poll_once(self, radio: Any, config: RadioConfig) -> None:
        started = time.perf_counter()
        frequency_hz = await _required_call(
            radio,
            "get_freq",
            config.command_timeout,
            0,
        )
        mode_result = await _required_call(
            radio,
            "get_mode",
            config.command_timeout,
            0,
        )
        mode, filter_num = mode_result

        optional: dict[str, Any] = {}
        commands = (
            ("data_mode", "get_data_mode", ()),
            ("s_meter", "get_s_meter", (0,)),
            ("swr", "get_swr", ()),
            ("power_level", "get_rf_power", ()),
            ("power_meter", "get_power_meter", ()),
            ("swr_meter", "get_swr_meter", ()),
            ("alc_meter", "get_alc_meter", ()),
            ("vd_meter", "get_vd_meter", ()),
            ("id_meter", "get_id_meter", ()),
            ("af_level", "get_af_level", (0,)),
            ("rf_gain", "get_rf_gain", (0,)),
            ("squelch", "get_squelch", (0,)),
            ("mic_gain", "get_mic_gain", ()),
        )
        for field, method_name, args in commands:
            optional[field] = await _optional_call(
                radio,
                method_name,
                config.command_timeout,
                *args,
            )

        state = getattr(radio, "radio_state", None)
        main = getattr(state, "main", None)
        active_vfo = str(getattr(main, "active_slot", "A") or "A")
        optional = _fill_from_state(optional, state, main)

        self._update(
            state="connected",
            connected=True,
            radio_ready=bool(getattr(radio, "radio_ready", True)),
            frequency_hz=int(frequency_hz),
            mode=str(mode),
            filter_num=filter_num,
            active_vfo=active_vfo,
            ptt=bool(getattr(state, "ptt", False)),
            split=bool(getattr(state, "split", False)),
            poll_latency_ms=round((time.perf_counter() - started) * 1000, 1),
            updated_epoch=time.time(),
            error="",
            **optional,
        )

    def _update(self, **values: Any) -> None:
        with self._lock:
            self._snapshot.update(values)


async def _required_call(
    radio: Any,
    method_name: str,
    timeout: float,
    *args: Any,
) -> Any:
    method = getattr(radio, method_name, None)
    if not callable(method):
        raise RuntimeError(f"Radio backend does not provide {method_name}()")
    return await asyncio.wait_for(method(*args), timeout=timeout)


async def _optional_call(
    radio: Any,
    method_name: str,
    timeout: float,
    *args: Any,
) -> Any:
    method = getattr(radio, method_name, None)
    if not callable(method):
        return None
    try:
        return await asyncio.wait_for(method(*args), timeout=timeout)
    except Exception:
        return None


def _fill_from_state(
    values: dict[str, Any],
    state: Any,
    main: Any,
) -> dict[str, Any]:
    fallbacks = {
        "s_meter": getattr(main, "s_meter", None),
        "af_level": getattr(main, "af_level", None),
        "rf_gain": getattr(main, "rf_gain", None),
        "squelch": getattr(main, "squelch", None),
        "power_level": getattr(state, "power_level", None),
        "power_meter": getattr(state, "power_meter", None),
        "swr_meter": getattr(state, "swr_meter", None),
        "alc_meter": getattr(state, "alc_meter", None),
        "vd_meter": getattr(state, "vd_meter", None),
        "id_meter": getattr(state, "id_meter", None),
        "mic_gain": getattr(state, "mic_gain", None),
        "data_mode": bool(getattr(main, "data_mode", False)),
    }
    for key, fallback in fallbacks.items():
        if values.get(key) is None and fallback is not None:
            values[key] = fallback
    return values


async def _sleep_interruptibly(stop_event: threading.Event, seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while not stop_event.is_set():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        await asyncio.sleep(min(remaining, 0.25))


_POLLER = SharedRadioPoller()


def render(
    widget_id: str,
    settings: dict[str, Any],
    station: dict[str, str],
) -> dict[str, Any]:
    if _RIGPLANE_IMPORT_ERROR:
        python_note = " Python 3.11 or newer is required." if sys.version_info < (3, 11) else ""
        return {
            "format": "message",
            "title": "IC-705 IP dependency missing",
            "status": "error",
            "message": (
                "Install the optional IC-705 IP dependency with "
                "pip install -e '.[icom-ip]'."
                f"{python_note} Import error: {_RIGPLANE_IMPORT_ERROR}"
            ),
        }

    try:
        config = RadioConfig.from_settings(settings)
        _POLLER.ensure_started(config)
    except Exception as exc:
        return {
            "format": "message",
            "title": "IC-705 IP configuration error",
            "status": "error",
            "message": str(exc),
        }

    snapshot = _POLLER.snapshot()
    return _render_widget(widget_id, snapshot, config, station)


def shutdown() -> None:
    _POLLER.stop()


def _render_widget(
    widget_id: str,
    snapshot: dict[str, Any],
    config: RadioConfig,
    station: dict[str, str],
) -> dict[str, Any]:
    age = _snapshot_age(snapshot)
    stale = age is None or age > config.stale_after
    connected = bool(snapshot.get("connected"))
    state = str(snapshot.get("state", "idle"))
    status = "good" if connected and not stale else "warning" if connected else "error"

    if not connected and snapshot.get("error"):
        state_label = "Offline"
    elif state in {"starting", "connecting", "idle"}:
        state_label = "Connecting"
        status = "warning"
    elif stale:
        state_label = "Stale"
    else:
        state_label = "Connected"

    if widget_id == "connection-health":
        metrics = [
            {"label": "Connection", "value": state_label, "status": status},
            {"label": "Endpoint", "value": f"{config.host}:{config.control_port}"},
            {"label": "CI-V", "value": f"0x{config.radio_address:02X}"},
            {"label": "Backend", "value": str(snapshot.get("backend", "rigplane-lan"))},
            {"label": "Poll latency", "value": _milliseconds(snapshot.get("poll_latency_ms"))},
            {"label": "Last update", "value": _age_text(age)},
        ]
        if snapshot.get("error"):
            metrics.append({"label": "Last error", "value": str(snapshot["error"]), "status": "error"})
        return {
            "format": "metrics",
            "title": "IC-705 Connection",
            "subtitle": f"Direct Wi-Fi control • {config.username}",
            "metrics": metrics,
        }

    frequency = _format_frequency(snapshot.get("frequency_hz"))
    mode = _format_mode(snapshot.get("mode"), snapshot.get("data_mode"))
    tx_state = "TX" if snapshot.get("ptt") else "RX"

    if widget_id == "radio-compact":
        return {
            "format": "metrics",
            "title": "Icom IC-705",
            "subtitle": f"{state_label} • {config.host}",
            "metrics": [
                {"label": "Frequency", "value": frequency, "status": status},
                {"label": "Mode", "value": mode},
                {"label": "VFO", "value": str(snapshot.get("active_vfo", "A"))},
                {"label": "State", "value": tx_state, "status": "warning" if tx_state == "TX" else "good"},
                {"label": "Callsign", "value": station.get("CALLSIGN", "")},
            ],
        }

    if widget_id == "radio-meters":
        return {
            "format": "metrics",
            "title": "IC-705 Meters",
            "subtitle": f"{frequency} • {mode}",
            "metrics": [
                {"label": "Signal", "value": _signal_text(snapshot.get("s_meter"))},
                {"label": "SWR", "value": _ratio(snapshot.get("swr"))},
                {"label": "Power meter", "value": _raw_meter(snapshot.get("power_meter"))},
                {"label": "SWR meter", "value": _raw_meter(snapshot.get("swr_meter"))},
                {"label": "ALC", "value": _raw_meter(snapshot.get("alc_meter"))},
                {"label": "Supply Vd", "value": _raw_meter(snapshot.get("vd_meter"))},
                {"label": "Drain Id", "value": _raw_meter(snapshot.get("id_meter"))},
                {"label": "Updated", "value": _age_text(age), "status": status},
            ],
        }

    power_level = snapshot.get("power_level")
    return {
        "format": "metrics",
        "title": "IC-705 Radio Status",
        "subtitle": f"Direct IP • {config.host}:{config.control_port}",
        "metrics": [
            {"label": "Frequency", "value": frequency, "status": status},
            {"label": "Mode", "value": mode},
            {"label": "Filter", "value": _filter_text(snapshot.get("filter_num"))},
            {"label": "VFO", "value": str(snapshot.get("active_vfo", "A"))},
            {"label": "Radio", "value": tx_state, "status": "warning" if tx_state == "TX" else "good"},
            {"label": "Split", "value": "On" if snapshot.get("split") else "Off"},
            {"label": "RF Power", "value": _power_text(power_level, config.max_watts)},
            {"label": "Volume", "value": _percent_255(snapshot.get("af_level"))},
            {"label": "RF Gain", "value": _percent_255(snapshot.get("rf_gain"))},
            {"label": "Mic Gain", "value": _percent_255(snapshot.get("mic_gain"))},
            {"label": "Squelch", "value": _percent_255(snapshot.get("squelch"))},
            {"label": "Signal", "value": _signal_text(snapshot.get("s_meter"))},
        ],
    }


def _snapshot_age(snapshot: dict[str, Any]) -> float | None:
    updated = float(snapshot.get("updated_epoch") or 0.0)
    if updated <= 0:
        return None
    return max(0.0, time.time() - updated)


def _format_frequency(value: Any) -> str:
    if value is None:
        return "Waiting…"
    hz = int(value)
    if hz >= 1_000_000_000:
        return f"{hz / 1_000_000_000:.6f} GHz"
    if hz >= 1_000_000:
        return f"{hz / 1_000_000:.6f} MHz"
    if hz >= 1_000:
        return f"{hz / 1_000:.3f} kHz"
    return f"{hz} Hz"


def _format_mode(mode: Any, data_mode: Any) -> str:
    text = str(mode or "Unknown")
    if bool(data_mode) and not text.endswith("-D"):
        return f"{text}-D"
    return text


def _filter_text(value: Any) -> str:
    return "N/A" if value is None else f"FIL{int(value)}"


def _percent_255(value: Any) -> str:
    if value is None:
        return "N/A"
    number = max(0.0, min(255.0, float(value)))
    return f"{number / 255.0 * 100:.0f}%"


def _power_text(value: Any, max_watts: float) -> str:
    if value is None:
        return "N/A"
    raw = max(0.0, min(255.0, float(value)))
    percent = raw / 255.0 * 100.0
    estimated = raw / 255.0 * max_watts
    return f"{percent:.0f}% • ~{estimated:.1f} W"


def _signal_text(value: Any) -> str:
    if value is None:
        return "N/A"
    raw = max(0.0, min(241.0, float(value)))
    return f"{raw / 241.0 * 100:.0f}% • raw {raw:.0f}"


def _raw_meter(value: Any) -> str:
    if value is None:
        return "N/A"
    raw = max(0.0, min(255.0, float(value)))
    return f"{raw / 255.0 * 100:.0f}% • raw {raw:.0f}"


def _ratio(value: Any) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.2f}:1"


def _milliseconds(value: Any) -> str:
    return "N/A" if value is None else f"{float(value):.0f} ms"


def _age_text(age: float | None) -> str:
    if age is None:
        return "Waiting…"
    if age < 1:
        return "Just now"
    if age < 60:
        return f"{age:.0f}s ago"
    if age < 3600:
        return f"{age / 60:.0f}m ago"
    return f"{age / 3600:.1f}h ago"
