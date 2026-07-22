from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.paths import ROOT_DIR, user_plugins_dir

PLUGIN_DIRS = [ROOT_DIR / "plugins", user_plugins_dir()]
PLUGIN_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SECRET_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")
ALLOWED_PERMISSIONS = {
    "network",
    "local-network",
    "filesystem",
    "device",
    "subprocess",
    "secrets",
}


def discover_plugins() -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for base in PLUGIN_DIRS:
        base.mkdir(parents=True, exist_ok=True)
        for manifest_path in sorted(base.glob("*/manifest.json")):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                plugin_id = str(manifest.get("id", ""))
                if not PLUGIN_ID.fullmatch(plugin_id):
                    continue
                permissions = [
                    str(value)
                    for value in manifest.get("permissions", [])
                    if str(value) in ALLOWED_PERMISSIONS
                ]
                secrets = []
                for secret in manifest.get("secrets", []):
                    if not isinstance(secret, dict):
                        continue
                    name = str(secret.get("name", ""))
                    if SECRET_NAME.fullmatch(name):
                        secrets.append(
                            {
                                "name": name,
                                "description": str(secret.get("description", "")),
                                "required": bool(secret.get("required", False)),
                            }
                        )
                manifest["permissions"] = sorted(set(permissions))
                manifest["secrets"] = secrets
                manifest["_path"] = str(manifest_path.parent)
                manifest.setdefault("version", "0.0.0")
                manifest.setdefault("author", "Unknown")
                manifest.setdefault("description", "")
                manifest.setdefault("widgets", [])
                found.append(manifest)
            except Exception:
                continue
    unique = {plugin["id"]: plugin for plugin in found}
    return sorted(
        unique.values(),
        key=lambda plugin: plugin.get("name", plugin["id"]).lower(),
    )


def get_plugin(plugin_id: str) -> dict[str, Any]:
    for plugin in discover_plugins():
        if plugin["id"] == plugin_id:
            return plugin
    raise FileNotFoundError(f"Plugin not found: {plugin_id}")


def public_plugin(
    plugin: dict[str, Any],
    enabled: bool = True,
    settings: dict | None = None,
    approvals: list[str] | None = None,
    secret_refs: dict[str, str] | None = None,
) -> dict[str, Any]:
    approvals = approvals or []
    secret_refs = secret_refs or {}
    required_permissions = list(plugin.get("permissions", []))
    permission_ready = set(required_permissions).issubset(set(approvals))
    secret_status = {
        secret["name"]: bool(
            secret_refs.get(secret["name"])
            and os.getenv(secret_refs[secret["name"]], "")
        )
        for secret in plugin.get("secrets", [])
    }
    required_secrets_ready = all(
        not secret.get("required") or secret_status.get(secret["name"], False)
        for secret in plugin.get("secrets", [])
    )
    return {
        key: value
        for key, value in plugin.items()
        if not key.startswith("_")
    } | {
        "enabled": enabled,
        "settings": settings or {},
        "approvals": approvals,
        "permission_ready": permission_ready,
        "secret_refs": secret_refs,
        "secret_status": secret_status,
        "required_secrets_ready": required_secrets_ready,
        "runtime_ready": permission_ready and required_secrets_ready,
    }


def _secret_environment(
    plugin: dict[str, Any],
    secret_refs: dict[str, str],
) -> dict[str, str]:
    environment: dict[str, str] = {}
    declared = {item["name"]: item for item in plugin.get("secrets", [])}
    for secret_name, env_name in secret_refs.items():
        if secret_name not in declared:
            continue
        value = os.getenv(env_name, "")
        if value:
            normalized = re.sub(r"[^A-Z0-9_]", "_", secret_name.upper())
            environment[f"DASHBOARD_MATRIX_SECRET_{normalized}"] = value
    missing = [
        name
        for name, definition in declared.items()
        if definition.get("required")
        and not environment.get(
            "DASHBOARD_MATRIX_SECRET_"
            + re.sub(r"[^A-Z0-9_]", "_", name.upper())
        )
    ]
    if missing:
        raise RuntimeError(
            "Required plugin secret is not configured: " + ", ".join(missing)
        )
    return environment


def run_plugin_widget(
    plugin_id: str,
    widget_id: str,
    settings: dict[str, Any],
    station: dict[str, str],
    *,
    approvals: list[str] | None = None,
    secret_refs: dict[str, str] | None = None,
    timeout_seconds: int = 20,
) -> dict[str, Any]:
    plugin = get_plugin(plugin_id)
    widget = next(
        (item for item in plugin.get("widgets", []) if item.get("id") == widget_id),
        None,
    )
    if not widget:
        raise KeyError(f"Unknown widget {widget_id}")

    approvals = [
        permission
        for permission in (approvals or [])
        if permission in ALLOWED_PERMISSIONS
    ]
    required = set(plugin.get("permissions", []))
    missing = sorted(required - set(approvals))
    if missing:
        raise PermissionError(
            "Plugin permissions have not been approved: " + ", ".join(missing)
        )

    module_path = Path(plugin["_path"]) / str(widget.get("module", "plugin.py"))
    plugin_root = Path(plugin["_path"]).resolve()
    resolved_module = module_path.resolve()
    if not resolved_module.is_relative_to(plugin_root) or not resolved_module.exists():
        raise FileNotFoundError("Plugin module not found")

    payload = {
        "plugin_id": plugin_id,
        "widget_id": widget_id,
        "module_path": str(resolved_module),
        "plugin_root": str(plugin_root),
        "settings": settings,
        "station": station,
        "approvals": approvals,
    }
    worker = ROOT_DIR / "app" / "plugin_worker.py"
    environment = {
        "PATH": os.getenv("PATH", ""),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
        "HOME": os.getenv("HOME", str(ROOT_DIR)),
        "TEMP": os.getenv("TEMP", os.getenv("TMP", "/tmp")),
    }
    environment.update(_secret_environment(plugin, secret_refs or {}))

    try:
        completed = subprocess.run(
            [sys.executable, "-I", str(worker)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=max(1, min(int(timeout_seconds), 120)),
            env=environment,
            cwd=str(plugin_root),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"Plugin timed out after {timeout_seconds} seconds") from exc

    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "Plugin worker failed"
        raise RuntimeError(message[-2000:])
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Plugin returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Plugin render() must return a dictionary")
    return result
