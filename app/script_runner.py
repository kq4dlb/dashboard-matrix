from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from app.paths import data_dir, user_scripts_dir
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
BUILTIN_SCRIPT_DIR = BASE_DIR / "user_scripts"
SCRIPT_DIR = user_scripts_dir()
DATA_DIR = data_dir()
SCRIPT_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
MAX_TIMEOUT = 60
MAX_OUTPUT_BYTES = 1_000_000


def available_scripts() -> list[dict[str, str]]:
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, str]] = []
    for base in dict.fromkeys([SCRIPT_DIR, BUILTIN_SCRIPT_DIR]):
        base.mkdir(parents=True, exist_ok=True)
        for path in sorted(base.glob("*.py")):
            if path.name.startswith("_") or any(item["name"] == path.stem for item in items):
                continue
            items.append({"name": path.stem, "filename": path.name})
    return items


def _resolve_script(name: str) -> Path:
    if not SCRIPT_NAME.fullmatch(name):
        raise ValueError("Invalid script name")
    for base in dict.fromkeys([SCRIPT_DIR, BUILTIN_SCRIPT_DIR]):
        path = (base / f"{name}.py").resolve()
        if path.parent == base.resolve() and path.is_file():
            return path
    raise FileNotFoundError(f"Script '{name}' was not found")


async def run_script(name: str, settings: dict[str, Any], station: dict[str, str]) -> dict[str, Any]:
    path = _resolve_script(name)
    timeout = max(1, min(int(settings.get("timeout_seconds", 20)), MAX_TIMEOUT))
    script_settings = settings.get("script_settings", {})
    if not isinstance(script_settings, dict):
        raise ValueError("script_settings must be a JSON object")

    env = os.environ.copy()
    env.update({
        "DASHBOARD_MATRIX_CALLSIGN": station["CALLSIGN"],
        "DASHBOARD_MATRIX_GRIDSQUARE": station["GRIDSQUARE"],
        "DASHBOARD_MATRIX_LAT": station["LAT"],
        "DASHBOARD_MATRIX_LONG": station["LONG"],
        "DASHBOARD_MATRIX_SCRIPT_SETTINGS": json.dumps(script_settings),
        "DASHBOARD_MATRIX_DATA_DIR": str(DATA_DIR),
        "PYTHONUNBUFFERED": "1",
    })
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(path),
        cwd=str(path.parent),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise TimeoutError(f"Script exceeded its {timeout}-second timeout")

    if len(stdout) > MAX_OUTPUT_BYTES:
        raise ValueError("Script output exceeded 1 MB")
    if proc.returncode != 0:
        detail = stderr.decode("utf-8", errors="replace").strip()[-1000:]
        raise RuntimeError(detail or f"Script exited with status {proc.returncode}")

    text = stdout.decode("utf-8", errors="replace").strip()
    if not text:
        return {"format": "text", "text": "Script completed without output"}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"format": "text", "text": text}
    if not isinstance(payload, dict):
        return {"format": "json", "data": payload}
    return payload
