#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: invalid JSON: {exc}"]

    if payload.get("schema_version") != 1:
        errors.append(f"{path}: unsupported schema_version")
    if payload.get("export_type") != "dashboard-matrix-layout":
        errors.append(f"{path}: export_type must be dashboard-matrix-layout")
    if not isinstance(payload.get("dashboards"), list):
        errors.append(f"{path}: dashboards must be an array")

    for dashboard in payload.get("dashboards", []):
        if not dashboard.get("slug"):
            errors.append(f"{path}: dashboard missing slug")
        if not isinstance(dashboard.get("tiles"), list):
            errors.append(
                f"{path}: dashboard {dashboard.get('slug')} tiles missing"
            )

    privacy = payload.get("privacy", {})
    if privacy.get("contains_admin_password"):
        errors.append(f"{path}: export claims to contain admin password")
    if privacy.get("contains_tokens"):
        errors.append(f"{path}: export claims to contain tokens")
    return errors


def main() -> int:
    root = Path("layouts")
    files = sorted(root.rglob("*.json")) if root.exists() else []
    all_errors = [error for path in files for error in validate(path)]

    if all_errors:
        print("\n".join(all_errors), file=sys.stderr)
        return 1

    print(f"Validated {len(files)} Dashboard Matrix layout export(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
