from __future__ import annotations

import builtins
import importlib.util
import json
import os
import socket
import subprocess
import sys
from pathlib import Path


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


def main() -> None:
    payload = json.loads(sys.stdin.read())
    module_path = Path(payload["module_path"]).resolve()
    plugin_root = Path(payload["plugin_root"]).resolve()
    if not module_path.is_relative_to(plugin_root):
        raise RuntimeError("Plugin module escaped its package directory")

    spec = importlib.util.spec_from_file_location(
        f"dashboard_matrix_plugin_{payload['plugin_id']}_{payload['widget_id']}",
        module_path,
    )
    if not spec or not spec.loader:
        raise RuntimeError("Unable to load plugin")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _install_guards(set(payload.get("approvals", [])), plugin_root)
    if not hasattr(module, "render"):
        raise RuntimeError("Plugin module must define render(widget_id, settings, station)")
    result = module.render(
        payload["widget_id"],
        payload.get("settings") or {},
        payload.get("station") or {},
    )
    if not isinstance(result, dict):
        raise RuntimeError("Plugin render() must return a dictionary")
    sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        raise SystemExit(1)
