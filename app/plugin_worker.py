from __future__ import annotations

import asyncio
import builtins
import importlib.util
import inspect
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, TextIO


def _deny(message: str):
    def denied(*args, **kwargs):
        raise PermissionError(message)

    return denied


def _install_guards(approvals: set[str], plugin_root: Path) -> None:
    if not ({"network", "local-network"} & approvals):
        socket.create_connection = _deny("Plugin network permission is not approved")
        socket.socket.connect = _deny("Plugin network permission is not approved")
        socket.socket.connect_ex = _deny("Plugin network permission is not approved")
    if "subprocess" not in approvals:
        subprocess.Popen = _deny("Plugin subprocess permission is not approved")
        subprocess.run = _deny("Plugin subprocess permission is not approved")
        subprocess.call = _deny("Plugin subprocess permission is not approved")
        subprocess.check_call = _deny("Plugin subprocess permission is not approved")
        subprocess.check_output = _deny("Plugin subprocess permission is not approved")
        os.system = _deny("Plugin subprocess permission is not approved")
    if "filesystem" not in approvals and "device" not in approvals:
        original_open = builtins.open

        def restricted_open(file, mode="r", *args, **kwargs):
            path = Path(file).expanduser().resolve()
            if path.is_relative_to(plugin_root) and all(flag not in mode for flag in "wax+"):
                return original_open(file, mode, *args, **kwargs)
            raise PermissionError("Plugin filesystem permission is not approved")

        builtins.open = restricted_open


def _load_module(payload: dict[str, Any]) -> tuple[ModuleType, Path, Path]:
    module_path = Path(payload["module_path"]).resolve()
    plugin_root = Path(payload["plugin_root"]).resolve()
    if not module_path.is_relative_to(plugin_root):
        raise RuntimeError("Plugin module escaped its package directory")

    module_name = f"dashboard_matrix_plugin_{payload['plugin_id']}_{module_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if not spec or not spec.loader:
        raise RuntimeError("Unable to load plugin")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "render"):
        raise RuntimeError("Plugin module must define render(widget_id, settings, station)")
    return module, module_path, plugin_root


def _render(module: ModuleType, payload: dict[str, Any]) -> dict[str, Any]:
    result = module.render(
        payload["widget_id"],
        payload.get("settings") or {},
        payload.get("station") or {},
    )
    if not isinstance(result, dict):
        raise RuntimeError("Plugin render() must return a dictionary")
    return result


def _shutdown_module(module: ModuleType) -> None:
    shutdown = getattr(module, "shutdown", None)
    if shutdown is None:
        return
    result = shutdown()
    if inspect.isawaitable(result):
        asyncio.run(result)


def _write_response(stream: TextIO, payload: dict[str, Any]) -> None:
    stream.write(json.dumps(payload, separators=(",", ":")) + "\n")
    stream.flush()


def persistent_main() -> None:
    # Reserve the original stdout for the JSON-lines protocol. Redirect all
    # plugin prints, including background-thread output, to stderr so a plugin
    # cannot corrupt the response stream.
    protocol_stdout = sys.stdout
    sys.stdout = sys.stderr

    module: ModuleType | None = None
    module_path: Path | None = None
    plugin_root: Path | None = None

    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise RuntimeError("Plugin worker payload must be an object")

                if module is None:
                    module, module_path, plugin_root = _load_module(payload)
                    _install_guards(
                        set(payload.get("approvals", [])),
                        plugin_root,
                    )
                else:
                    requested_module = Path(payload["module_path"]).resolve()
                    requested_root = Path(payload["plugin_root"]).resolve()
                    if requested_module != module_path or requested_root != plugin_root:
                        raise RuntimeError("Persistent worker received a different plugin module")

                _write_response(
                    protocol_stdout,
                    {"ok": True, "result": _render(module, payload)},
                )
            except Exception as exc:
                _write_response(
                    protocol_stdout,
                    {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                )
    finally:
        if module is not None:
            try:
                _shutdown_module(module)
            except Exception as exc:
                sys.stderr.write(f"Plugin shutdown error: {type(exc).__name__}: {exc}\n")


def main() -> None:
    payload = json.loads(sys.stdin.read())
    module, _, plugin_root = _load_module(payload)
    _install_guards(set(payload.get("approvals", [])), plugin_root)
    sys.stdout.write(json.dumps(_render(module, payload)))


if __name__ == "__main__":
    try:
        if "--persistent" in sys.argv[1:]:
            persistent_main()
        else:
            main()
    except Exception as exc:
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        raise SystemExit(1)
