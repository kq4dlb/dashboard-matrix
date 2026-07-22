#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import init_db
from app.layout_exports import (
    TOKEN_ENV,
    build_layout_export,
    publish_layout_export,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export Dashboard Matrix dashboards and card layouts."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON path. Defaults to a timestamped file.",
    )
    parser.add_argument(
        "--include-station",
        action="store_true",
        help="Include callsign, grid, and map-profile station settings.",
    )
    parser.add_argument("--title", default="")
    parser.add_argument("--description", default="")
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Repeat for multiple tags.",
    )
    parser.add_argument(
        "--screenshot",
        type=Path,
        help="Optional PNG/JPEG screenshot to publish with the layout.",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish the export to GitHub after writing it locally.",
    )
    parser.add_argument(
        "--repository",
        default=os.getenv(
            "DASHBOARD_MATRIX_LAYOUT_GITHUB_REPOSITORY",
            "KQ4DLB/dashboard-matrix-exchange",
        ),
    )
    parser.add_argument(
        "--branch",
        default=os.getenv("DASHBOARD_MATRIX_LAYOUT_GITHUB_BRANCH", "main"),
    )
    parser.add_argument(
        "--folder",
        default=os.getenv("DASHBOARD_MATRIX_LAYOUT_GITHUB_FOLDER", "layouts"),
    )
    args = parser.parse_args()

    init_db()
    export_data = build_layout_export(
        include_station=args.include_station,
        metadata={
            "title": args.title,
            "description": args.description,
            "tags": args.tag,
        },
    )

    if args.output:
        output = args.output
    else:
        from app.layout_exports import _slugify, _utc_stamp

        callsign = _slugify(
            export_data["author"].get("callsign", "n0call"),
            "n0call",
        )
        output = Path(
            f"{_utc_stamp()}-{callsign}-dashboard-matrix-layout.json"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(export_data, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Wrote {output}")

    if not args.publish:
        return 0

    token = os.getenv(TOKEN_ENV, "")
    if not token:
        print(
            f"ERROR: set {TOKEN_ENV} before publishing",
            file=sys.stderr,
        )
        return 2

    screenshot = None
    if args.screenshot:
        raw = args.screenshot.read_bytes()
        suffix = args.screenshot.suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg"}:
            print("ERROR: screenshot must be PNG or JPEG", file=sys.stderr)
            return 2
        screenshot = (raw, "png" if suffix == ".png" else "jpg")

    result = publish_layout_export(
        export_data=export_data,
        repository=args.repository,
        branch=args.branch,
        folder=args.folder,
        token=token,
        screenshot=screenshot,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
