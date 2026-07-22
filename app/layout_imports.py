from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_admin
from app.database import connection, row_to_dict, set_setting
from app.websocket import manager

router = APIRouter(prefix="/api/layout-imports", tags=["layout-imports"])

ALLOWED_TILE_TYPES = {
    "iframe",
    "image",
    "rotation",
    "text",
    "clock",
    "status",
    "provider",
    "script",
    "plugin",
}


class LayoutAnalyzeRequest(BaseModel):
    document: dict[str, Any]


class LayoutImportRequest(BaseModel):
    document: dict[str, Any]
    conflict_strategy: Literal["rename", "replace", "skip", "merge"] = "rename"
    include_station: bool = False
    source_name: str = Field(default="uploaded-layout.json", max_length=255)


def _slugify(value: str, fallback: str = "imported-dashboard") -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result or fallback


def _validate_document(document: dict[str, Any]) -> list[dict[str, Any]]:
    if document.get("export_type") != "dashboard-matrix-layout":
        raise HTTPException(422, "Not a Dashboard Matrix layout export")
    if int(document.get("schema_version", 0)) != 1:
        raise HTTPException(422, "Unsupported layout schema version")
    dashboards = document.get("dashboards")
    if not isinstance(dashboards, list) or not dashboards:
        raise HTTPException(422, "The layout export contains no dashboards")

    clean: list[dict[str, Any]] = []
    for index, dashboard in enumerate(dashboards):
        if not isinstance(dashboard, dict):
            raise HTTPException(422, f"Dashboard #{index + 1} is invalid")
        name = str(dashboard.get("name") or f"Imported Dashboard {index + 1}")[:120]
        slug = _slugify(str(dashboard.get("slug") or name))[:80]
        tiles = dashboard.get("tiles") or []
        if not isinstance(tiles, list):
            raise HTTPException(422, f"Dashboard {name} has an invalid card list")
        clean_tiles: list[dict[str, Any]] = []
        for tile_index, tile in enumerate(tiles):
            if not isinstance(tile, dict):
                raise HTTPException(
                    422,
                    f"Card #{tile_index + 1} in {name} is invalid",
                )
            tile_type = str(tile.get("type") or tile.get("tile_type") or "iframe")
            if tile_type not in ALLOWED_TILE_TYPES:
                raise HTTPException(
                    422,
                    f"Card {tile.get('title', tile_index + 1)} uses unsupported type {tile_type}",
                )
            sources = tile.get("sources") or []
            if not isinstance(sources, list) or any(
                not isinstance(source, str) for source in sources
            ):
                raise HTTPException(422, f"Card sources in {name} must be strings")
            settings = tile.get("settings") or {}
            if not isinstance(settings, dict):
                raise HTTPException(422, f"Card settings in {name} must be an object")
            show_title = tile.get("show_title", "auto")
            settings = deepcopy(settings)
            if show_title == "show":
                settings["show_title"] = True
            elif show_title == "hide":
                settings["show_title"] = False
            clean_tiles.append(
                {
                    "title": str(tile.get("title") or "Imported Card")[:120],
                    "tile_type": tile_type,
                    "sources": sources,
                    "row_pos": max(1, int(tile.get("y", tile.get("row_pos", 1)))),
                    "col_pos": max(1, int(tile.get("x", tile.get("col_pos", 1)))),
                    "width": min(12, max(1, int(tile.get("width", 1)))),
                    "height": min(24, max(1, int(tile.get("height", 1)))),
                    "refresh_seconds": min(
                        86400,
                        max(0, int(tile.get("refresh_seconds", 300))),
                    ),
                    "rotate_seconds": min(
                        86400,
                        max(0, int(tile.get("rotate_seconds", 0))),
                    ),
                    "enabled": bool(tile.get("enabled", True)),
                    "locked": bool(tile.get("locked", False)),
                    "settings": settings,
                }
            )
        clean.append(
            {
                "name": name,
                "slug": slug,
                "columns": min(12, max(1, int(dashboard.get("columns", 4)))),
                "rows": min(24, max(1, int(dashboard.get("rows", 3)))),
                "rotate_seconds": min(
                    86400,
                    max(
                        0,
                        int(
                            dashboard.get(
                                "rotation_seconds",
                                dashboard.get("rotate_seconds", 0),
                            )
                        ),
                    ),
                ),
                "is_default": bool(dashboard.get("is_default", False)),
                "enabled": bool(dashboard.get("enabled", True)),
                "sort_order": max(0, int(dashboard.get("sort_order", index))),
                "tiles": clean_tiles,
            }
        )
    return clean


def analyze_layout(document: dict[str, Any]) -> dict[str, Any]:
    dashboards = _validate_document(document)
    with connection() as conn:
        existing = {
            row["slug"]: row_to_dict(row)
            for row in conn.execute("SELECT * FROM dashboards").fetchall()
        }
    conflicts = []
    for dashboard in dashboards:
        if dashboard["slug"] in existing:
            conflicts.append(
                {
                    "slug": dashboard["slug"],
                    "incoming_name": dashboard["name"],
                    "existing_name": existing[dashboard["slug"]]["name"],
                }
            )
    requirements = document.get("requirements") or {}
    return {
        "valid": True,
        "schema_version": 1,
        "dashboard_count": len(dashboards),
        "card_count": sum(len(item["tiles"]) for item in dashboards),
        "conflicts": conflicts,
        "requirements": {
            "plugins": list(requirements.get("plugins") or []),
            "scripts": list(requirements.get("scripts") or []),
            "external_sources": list(requirements.get("external_sources") or []),
        },
        "contains_station": bool(
            (document.get("author") or {}).get("station")
        ),
    }


def _unique_slug(conn, slug: str) -> str:
    candidate = slug
    suffix = 2
    while conn.execute(
        "SELECT 1 FROM dashboards WHERE slug=?",
        (candidate,),
    ).fetchone():
        candidate = f"{slug[:70]}-{suffix}"
        suffix += 1
    return candidate


def _insert_tiles(conn, dashboard_id: int, tiles: list[dict[str, Any]], row_offset: int = 0) -> int:
    count = 0
    for tile in tiles:
        conn.execute(
            """
            INSERT INTO tiles(
                dashboard_id,title,tile_type,sources_json,row_pos,col_pos,
                width,height,locked,refresh_seconds,rotate_seconds,enabled,
                settings_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                dashboard_id,
                tile["title"],
                tile["tile_type"],
                json.dumps(tile["sources"]),
                tile["row_pos"] + row_offset,
                tile["col_pos"],
                tile["width"],
                tile["height"],
                int(tile["locked"]),
                tile["refresh_seconds"],
                tile["rotate_seconds"],
                int(tile["enabled"]),
                json.dumps(tile["settings"]),
            ),
        )
        count += 1
    return count


@router.post("/analyze")
def analyze_endpoint(
    item: LayoutAnalyzeRequest,
    _: None = Depends(require_admin),
) -> dict[str, Any]:
    return analyze_layout(item.document)


@router.post("")
async def import_endpoint(
    item: LayoutImportRequest,
    _: None = Depends(require_admin),
) -> dict[str, Any]:
    dashboards = _validate_document(item.document)
    result = {
        "created": [],
        "replaced": [],
        "merged": [],
        "renamed": [],
        "skipped": [],
        "cards_imported": 0,
    }

    with connection() as conn:
        for dashboard in dashboards:
            existing = conn.execute(
                "SELECT * FROM dashboards WHERE slug=?",
                (dashboard["slug"],),
            ).fetchone()

            if existing and item.conflict_strategy == "skip":
                result["skipped"].append(dashboard["slug"])
                continue

            if existing and item.conflict_strategy == "replace":
                dashboard_id = int(existing["id"])
                if dashboard["is_default"]:
                    conn.execute("UPDATE dashboards SET is_default=0 WHERE id<>?", (dashboard_id,))
                conn.execute("DELETE FROM tiles WHERE dashboard_id=?", (dashboard_id,))
                conn.execute(
                    """
                    UPDATE dashboards SET
                        name=?,columns=?,rows=?,rotate_seconds=?,is_default=?,
                        enabled=?,sort_order=?
                    WHERE id=?
                    """,
                    (
                        dashboard["name"],
                        dashboard["columns"],
                        dashboard["rows"],
                        dashboard["rotate_seconds"],
                        int(dashboard["is_default"]),
                        int(dashboard["enabled"]),
                        dashboard["sort_order"],
                        dashboard_id,
                    ),
                )
                result["cards_imported"] += _insert_tiles(
                    conn,
                    dashboard_id,
                    dashboard["tiles"],
                )
                result["replaced"].append(dashboard["slug"])
                continue

            if existing and item.conflict_strategy == "merge":
                dashboard_id = int(existing["id"])
                max_row = conn.execute(
                    """
                    SELECT COALESCE(MAX(row_pos + height - 1),0)
                    FROM tiles WHERE dashboard_id=?
                    """,
                    (dashboard_id,),
                ).fetchone()[0]
                result["cards_imported"] += _insert_tiles(
                    conn,
                    dashboard_id,
                    dashboard["tiles"],
                    row_offset=int(max_row),
                )
                result["merged"].append(dashboard["slug"])
                continue

            slug = dashboard["slug"]
            if existing:
                new_slug = _unique_slug(conn, slug)
                result["renamed"].append({"from": slug, "to": new_slug})
                slug = new_slug

            if dashboard["is_default"]:
                conn.execute("UPDATE dashboards SET is_default=0")
            dashboard_id = conn.execute(
                """
                INSERT INTO dashboards(
                    name,slug,columns,rows,rotate_seconds,is_default,enabled,
                    sort_order
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    dashboard["name"],
                    slug,
                    dashboard["columns"],
                    dashboard["rows"],
                    dashboard["rotate_seconds"],
                    int(dashboard["is_default"]),
                    int(dashboard["enabled"]),
                    dashboard["sort_order"],
                ),
            ).lastrowid
            result["cards_imported"] += _insert_tiles(
                conn,
                int(dashboard_id),
                dashboard["tiles"],
            )
            result["created"].append(slug)

        if item.include_station:
            station = (item.document.get("author") or {}).get("station") or {}
            for key in (
                "callsign",
                "grid_square",
                "map_profile",
                "map_zoom",
                "map_radius_miles",
                "map_custom_latitude",
                "map_custom_longitude",
            ):
                if key in station:
                    set_setting(conn, key, str(station[key]))

        conn.execute(
            """
            INSERT INTO layout_import_history(
                source_name,conflict_strategy,result_json
            ) VALUES(?,?,?)
            """,
            (
                item.source_name,
                item.conflict_strategy,
                json.dumps(result),
            ),
        )

        if conn.execute(
            "SELECT COUNT(*) FROM dashboards WHERE is_default=1"
        ).fetchone()[0] == 0:
            first = conn.execute(
                "SELECT id FROM dashboards ORDER BY sort_order,id LIMIT 1"
            ).fetchone()
            if first:
                conn.execute(
                    "UPDATE dashboards SET is_default=1 WHERE id=?",
                    (first["id"],),
                )

    await manager.broadcast({"event": "configuration_changed"})
    return result
