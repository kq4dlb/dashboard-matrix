from __future__ import annotations

import asyncio
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from app.paths import data_dir

HAMQSL_URL = "https://www.hamqsl.com/solarxml.php"
DEFAULT_INTERVAL = 600
DATA_DIR = data_dir()
CACHE_FILE = DATA_DIR / "hamqsl_solar.xml"
STATUS_FILE = DATA_DIR / "hamqsl_status.json"


def _write_status(**values: object) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    current: dict[str, object] = {}
    if STATUS_FILE.exists():
        try:
            current = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            current = {}
    current.update(values)
    current["status_written_epoch"] = int(time.time())
    STATUS_FILE.write_text(json.dumps(current, indent=2), encoding="utf-8")


def fetch_once() -> bool:
    """Fetch HamQSL XML and preserve the last-known-good copy."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    started = int(time.time())
    try:
        request = urllib.request.Request(
            HAMQSL_URL,
            headers={
                "User-Agent": "Dashboard-Matrix/0.1.0-beta (+local dashboard)",
                "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.8",
            },
        )
        context = ssl.create_default_context()
        with urllib.request.urlopen(request, timeout=20, context=context) as response:
            data = response.read(2_000_000)
        if b"<solardata" not in data:
            raise ValueError("HamQSL response did not contain a solardata element")
        temporary = CACHE_FILE.with_suffix(".xml.tmp")
        temporary.write_bytes(data)
        temporary.replace(CACHE_FILE)
        _write_status(
            ok=True,
            source=HAMQSL_URL,
            last_attempt_epoch=started,
            last_success_epoch=int(time.time()),
            bytes=len(data),
            error="",
        )
        return True
    except urllib.error.HTTPError as exc:
        detail = f"HTTP {exc.code}: {exc.reason}"
    except urllib.error.URLError as exc:
        detail = f"Network error: {exc.reason}"
    except ssl.SSLError as exc:
        detail = f"TLS error: {exc}"
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"
    _write_status(
        ok=False,
        source=HAMQSL_URL,
        last_attempt_epoch=started,
        cache_available=CACHE_FILE.exists(),
        error=detail,
    )
    return False


async def collector_loop(interval_seconds: int | None = None) -> None:
    interval = interval_seconds or int(os.getenv("DASHBOARD_MATRIX_HAMQSL_INTERVAL", DEFAULT_INTERVAL))
    interval = max(60, interval)
    while True:
        await asyncio.to_thread(fetch_once)
        await asyncio.sleep(interval)
