from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def layouts() -> list[dict]:
    items = []
    for path in sorted((ROOT / "layouts").glob("**/*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("export_type") != "dashboard-matrix-layout":
            continue
        screenshot = next(
            (candidate for candidate in (path.with_suffix(".png"), path.with_suffix(".jpg")) if candidate.exists()),
            None,
        )
        metadata = data.get("metadata") or {}
        items.append({
            "id": path.relative_to(ROOT).with_suffix("").as_posix().replace("/", "-"),
            "kind": "layout",
            "name": metadata.get("title") or path.stem,
            "description": metadata.get("description", ""),
            "author": (data.get("author") or {}).get("callsign", "Unknown"),
            "version": data.get("dashboard_matrix_version", "unknown"),
            "path": path.relative_to(ROOT).as_posix(),
            "screenshot": screenshot.relative_to(ROOT).as_posix() if screenshot else None,
            "tags": metadata.get("tags") or [],
        })
    return items


def packages() -> list[dict]:
    items = []
    for kind in ("plugins", "themes", "map-providers"):
        for path in sorted((ROOT / kind).glob("*/manifest.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("kind", {"plugins": "plugin", "themes": "theme", "map-providers": "map-provider"}[kind])
            data["manifest_path"] = path.relative_to(ROOT).as_posix()
            items.append(data)
    return items


index = {
    "schema_version": 1,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "items": layouts() + packages(),
}
(ROOT / "index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"Indexed {len(index['items'])} item(s)")
