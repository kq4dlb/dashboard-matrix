from __future__ import annotations

import atexit
import hashlib
import json
import os
import queue
import re
import shlex
import subprocess
import sys
import threading
from collections import deque
from pathlib import Path
from typing import Any

from app.paths import ROOT_DIR, user_plugins_dir

PLUGIN_DIRS = [ROOT_DIR / "plugins", user_plugins_dir()]
PLUGIN_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SECRET_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ALLOWED_PERMISSIONS = {
    "network",
    "local-network",
    "filesystem",
    "device",
    "subprocess",
    "secrets",
}


def _parse_env_file(path: Path) -> dict[str, str]:
    """Read simple KEY=value entries without executing shell code."""
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return values

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        name, raw_value = line.split("=", 1)
        name = name.strip()
        if not ENV_NAME.fullmatch(name):
            continue
        try:
            lexer = shlex.shlex(raw_value, posix=True)
            lexer.whitespace_split = True
            lexer.commenters = "#"
            tokens = list(lexer)
        except ValueError:
            continue
        values[name] = " ".join(tokens) if tokens else ""
    return values


def _candidate_env_files() -> list[Path]:
    candidates: list[Path] = []
    explicit = os.getenv("DASHBOARD_MATRIX_ENV_FILE", "").strip()
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.extend(
        [
            Path("/etc/dashboard-matrix.env"),
            ROOT_DIR / ".env",
            ROOT_DIR / "dashboard-matrix.env",
        ]
    )
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _resolve_secret_reference(reference: str) -> str:
    """Resolve an Admin secret mapping from env, env files, or file:PATH."""
    reference = str(reference or "").strip()
    if not reference:
        return ""

    if reference.startswith("file:"):
        secret_path = Path(reference[5:].strip()).expanduser()
        try:
            return secret_path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            return ""

    value = os.getenv(reference, "")
    if value:
        return value

    if ENV_NAME.fullmatch(reference):
        for env_file in _candidate_env_files():
            value = _parse_env_file(env_file).get(reference, "")
            if value:
                return value
    return ""


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
            _resolve_secret_reference(secret_refs.get(secret["name"], ""))
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
        value = _resolve_secret_reference(env_name)
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


class _PersistentPluginWorker:
    def __init__(
        self,
        *,
        worker_script: Path,
        plugin_root: Path,
        environment: dict[str, str],
    ) -> None:
        self._lock = threading.Lock()
        self._responses: queue.Queue[str | None] = queue.Queue()
        self._stderr_lines: deque[str] = deque(maxlen=80)
        self._process = subprocess.Popen(
            [sys.executable, "-I", str(worker_script), "--persistent"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=environment,
            cwd=str(plugin_root),
        )
        self._stdout_thread = threading.Thread(
            target=self._read_stdout,
            name="dashboard-plugin-stdout",
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._read_stderr,
            name="dashboard-plugin-stderr",
            daemon=True,
        )
        self._stdout_thread.start()
        self._stderr_thread.start()

    @property
    def alive(self) -> bool:
        return self._process.poll() is None

    def _read_stdout(self) -> None:
        assert self._process.stdout is not None
        try:
            for line in self._process.stdout:
                self._responses.put(line)
        finally:
            self._responses.put(None)

    def _read_stderr(self) -> None:
        assert self._process.stderr is not None
        for line in self._process.stderr:
            self._stderr_lines.append(line.rstrip())

    def _last_error(self) -> str:
        return "\n".join(self._stderr_lines)[-2000:]

    def request(self, payload: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
        timeout = max(1, min(int(timeout_seconds), 120))
        with self._lock:
            if not self.alive:
                raise RuntimeError(self._last_error() or "Plugin worker is not running")
            assert self._process.stdin is not None
            try:
                self._process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
                self._process.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                raise RuntimeError(self._last_error() or "Plugin worker pipe closed") from exc

            try:
                line = self._responses.get(timeout=timeout)
            except queue.Empty as exc:
                self.close()
                raise TimeoutError(f"Plugin timed out after {timeout_seconds} seconds") from exc

            if line is None:
                raise RuntimeError(self._last_error() or "Plugin worker exited")
            try:
                response = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError("Plugin worker returned invalid JSON") from exc
            if not isinstance(response, dict):
                raise RuntimeError("Plugin worker response must be an object")
            if not response.get("ok"):
                raise RuntimeError(str(response.get("error") or "Plugin worker failed")[-2000:])
            result = response.get("result")
            if not isinstance(result, dict):
                raise RuntimeError("Plugin render() must return a dictionary")
            return result

    def close(self) -> None:
        process = self._process
        if process.poll() is not None:
            return
        try:
            if process.stdin is not None:
                process.stdin.close()
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)


_WORKERS: dict[tuple[str, str, int, tuple[str, ...], str], _PersistentPluginWorker] = {}
_WORKERS_LOCK = threading.Lock()


def _worker_environment(
    plugin: dict[str, Any],
    secret_refs: dict[str, str],
) -> dict[str, str]:
    environment = {
        "PATH": os.getenv("PATH", ""),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
        "HOME": os.getenv("HOME", str(ROOT_DIR)),
        "TEMP": os.getenv("TEMP", os.getenv("TMP", "/tmp")),
    }
    environment.update(_secret_environment(plugin, secret_refs))
    return environment


def _run_one_shot_worker(
    *,
    payload: dict[str, Any],
    plugin_root: Path,
    environment: dict[str, str],
    timeout_seconds: int,
) -> dict[str, Any]:
    worker_script = ROOT_DIR / "app" / "plugin_worker.py"
    try:
        completed = subprocess.run(
            [sys.executable, "-I", str(worker_script)],
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


def _environment_fingerprint(environment: dict[str, str]) -> str:
    secret_values = {
        key: value
        for key, value in environment.items()
        if key.startswith("DASHBOARD_MATRIX_SECRET_")
    }
    serialized = json.dumps(secret_values, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _get_persistent_worker(
    *,
    plugin_id: str,
    module_path: Path,
    plugin_root: Path,
    approvals: list[str],
    environment: dict[str, str],
) -> _PersistentPluginWorker:
    module_mtime = module_path.stat().st_mtime_ns
    key = (
        plugin_id,
        str(module_path),
        module_mtime,
        tuple(sorted(approvals)),
        _environment_fingerprint(environment),
    )
    stale_workers: list[_PersistentPluginWorker] = []
    with _WORKERS_LOCK:
        worker = _WORKERS.get(key)
        if worker is not None and worker.alive:
            return worker
        if worker is not None:
            _WORKERS.pop(key, None)
            stale_workers.append(worker)

        # A permission, secret, or source-code change must replace the old
        # process so it cannot retain stale credentials or plugin state.
        for old_key, old_worker in list(_WORKERS.items()):
            if old_key[0] == plugin_id and old_key[1] == str(module_path):
                _WORKERS.pop(old_key, None)
                stale_workers.append(old_worker)

        worker_script = ROOT_DIR / "app" / "plugin_worker.py"
        worker = _PersistentPluginWorker(
            worker_script=worker_script,
            plugin_root=plugin_root,
            environment=environment,
        )
        _WORKERS[key] = worker

    for stale in stale_workers:
        stale.close()
    return worker


def shutdown_plugin_workers() -> None:
    with _WORKERS_LOCK:
        workers = list(_WORKERS.values())
        _WORKERS.clear()
    for worker in workers:
        worker.close()


atexit.register(shutdown_plugin_workers)


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
    environment = _worker_environment(plugin, secret_refs or {})
    if not bool(plugin.get("persistent_worker", False)):
        return _run_one_shot_worker(
            payload=payload,
            plugin_root=plugin_root,
            environment=environment,
            timeout_seconds=timeout_seconds,
        )

    worker = _get_persistent_worker(
        plugin_id=plugin_id,
        module_path=resolved_module,
        plugin_root=plugin_root,
        approvals=approvals,
        environment=environment,
    )
    return worker.request(payload, timeout_seconds)
