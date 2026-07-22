from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auth import require_admin
from app.database import connection, get_station_settings, row_to_dict
from app.version import APP_VERSION

router = APIRouter(prefix="/api/layout-exports", tags=["layout-exports"])

EXPORT_SCHEMA_VERSION = 1
TOKEN_ENV = "DASHBOARD_MATRIX_LAYOUT_GITHUB_TOKEN"
MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024
MAX_LAYOUT_BYTES = 5 * 1024 * 1024

SAFE_STATION_KEYS = {
    "callsign",
    "grid_square",
    "map_profile",
    "map_zoom",
    "map_radius_miles",
    "map_custom_latitude",
    "map_custom_longitude",
}

PUBLISH_SETTING_KEYS = {
    "repository": "layout_share_repository",
    "branch": "layout_share_branch",
    "folder": "layout_share_folder",
}


class ShareMetadata(BaseModel):
    title: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class PublishRequest(BaseModel):
    repository: str = Field(
        default="KQ4DLB/dashboard-matrix-exchange",
        pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
    )
    branch: str = Field(default="main", min_length=1, max_length=100)
    folder: str = Field(default="layouts", min_length=1, max_length=200)
    token: str | None = Field(default=None, repr=False)
    include_station: bool = False
    metadata: ShareMetadata = Field(default_factory=ShareMetadata)
    screenshot_data_url: str | None = None
    document: dict[str, Any] | None = None


class PublishSettingsUpdate(BaseModel):
    repository: str = Field(
        default="KQ4DLB/dashboard-matrix-exchange",
        pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
    )
    branch: str = Field(default="main", min_length=1, max_length=100)
    folder: str = Field(default="layouts", min_length=1, max_length=200)
    auto_publish: bool = False


def _slugify(value: str, fallback: str = "dashboard-matrix-layout") -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or fallback


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _clean_folder(folder: str) -> str:
    parts = [
        _slugify(part, "layouts")
        for part in folder.replace("\\", "/").split("/")
        if part.strip()
    ]
    return "/".join(parts) or "layouts"


def _tile_export(tile: dict[str, Any], dashboard_slug: str) -> dict[str, Any]:
    settings = tile.get("settings") or {}
    show_title = settings.get("show_title")
    if show_title is True:
        title_mode = "show"
    elif show_title is False:
        title_mode = "hide"
    else:
        title_mode = "auto"

    return {
        "preset_id": _slugify(
            f"{dashboard_slug}-{tile.get('title', 'tile')}-{tile.get('id')}"
        ),
        "title": tile.get("title", "Tile"),
        "type": tile.get("tile_type", "iframe"),
        "x": int(tile.get("col_pos", 1)),
        "y": int(tile.get("row_pos", 1)),
        "width": int(tile.get("width", 1)),
        "height": int(tile.get("height", 1)),
        "refresh_seconds": int(tile.get("refresh_seconds", 300)),
        "rotate_seconds": int(tile.get("rotate_seconds", 0)),
        "enabled": bool(tile.get("enabled", True)),
        "locked": bool(tile.get("locked", False)),
        "show_title": title_mode,
        "sources": tile.get("sources") or [],
        "settings": settings,
    }


def build_layout_export(
    *,
    include_station: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with connection() as conn:
        station = get_station_settings(conn)
        dashboard_rows = conn.execute(
            """
            SELECT *
            FROM dashboards
            ORDER BY sort_order, id
            """
        ).fetchall()

        dashboards: list[dict[str, Any]] = []
        plugin_requirements: set[str] = set()
        script_requirements: set[str] = set()
        external_sources: set[str] = set()

        for dashboard_row in dashboard_rows:
            dashboard = row_to_dict(dashboard_row)
            tile_rows = conn.execute(
                """
                SELECT *
                FROM tiles
                WHERE dashboard_id=?
                ORDER BY row_pos, col_pos, id
                """,
                (dashboard["id"],),
            ).fetchall()

            tiles: list[dict[str, Any]] = []
            for tile_row in tile_rows:
                tile = row_to_dict(tile_row)
                exported = _tile_export(tile, dashboard["slug"])
                tiles.append(exported)

                settings = exported["settings"]
                if exported["type"] == "plugin" and settings.get("plugin"):
                    plugin_requirements.add(str(settings["plugin"]))
                if exported["type"] == "script" and settings.get("script"):
                    script_requirements.add(str(settings["script"]))

                for source in exported["sources"]:
                    if isinstance(source, str) and (
                        source.startswith("http://")
                        or source.startswith("https://")
                        or source.startswith("proxy://")
                        or source.startswith("nws-radar://")
                    ):
                        external_sources.add(source)

            dashboards.append(
                {
                    "name": dashboard["name"],
                    "slug": dashboard["slug"],
                    "columns": int(dashboard.get("columns", 4)),
                    "rows": int(dashboard.get("rows", 3)),
                    "rotation_seconds": int(
                        dashboard.get("rotate_seconds", 0)
                    ),
                    "is_default": bool(dashboard.get("is_default", False)),
                    "enabled": bool(dashboard.get("enabled", True)),
                    "sort_order": int(dashboard.get("sort_order", 0)),
                    "tiles": tiles,
                }
            )

    author: dict[str, Any] = {
        "callsign": station.get("callsign", "N0CALL").upper(),
    }
    if include_station:
        author["station"] = {
            key: station[key]
            for key in sorted(SAFE_STATION_KEYS)
            if key in station
        }

    supplied_metadata = metadata or {}
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "export_type": "dashboard-matrix-layout",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dashboard_matrix_version": APP_VERSION,
        "author": author,
        "metadata": {
            "title": supplied_metadata.get("title", ""),
            "description": supplied_metadata.get("description", ""),
            "tags": supplied_metadata.get("tags", []),
        },
        "dashboards": dashboards,
        "requirements": {
            "plugins": sorted(plugin_requirements),
            "scripts": sorted(script_requirements),
            "external_sources": sorted(external_sources),
        },
        "privacy": {
            "contains_admin_password": False,
            "contains_tokens": False,
            "contains_station_location": include_station,
        },
    }



def _validated_publish_document(document: dict[str, Any]) -> dict[str, Any]:
    if document.get("export_type") != "dashboard-matrix-layout":
        raise ValueError("Published document is not a Dashboard Matrix layout export")
    if document.get("schema_version") != EXPORT_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported layout schema version: {document.get('schema_version')}"
        )
    if not isinstance(document.get("dashboards"), list):
        raise ValueError("Published layout must contain a dashboards list")
    encoded = json.dumps(document, sort_keys=True).encode("utf-8")
    if len(encoded) > MAX_LAYOUT_BYTES:
        raise ValueError("Layout export exceeds the 5 MB limit")
    return document

def _github_put_file(
    *,
    repository: str,
    branch: str,
    path: str,
    content: bytes,
    message: str,
    token: str,
) -> dict[str, Any]:
    endpoint = (
        f"https://api.github.com/repos/{repository}/contents/{path}"
    )
    payload = json.dumps(
        {
            "message": message,
            "content": base64.b64encode(content).decode("ascii"),
            "branch": branch,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="PUT",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"Dashboard-Matrix/{APP_VERSION} layout-publisher",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub returned HTTP {exc.code}: {details[:1000]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Unable to reach GitHub: {exc.reason}") from exc


def _decode_screenshot(data_url: str | None) -> tuple[bytes, str] | None:
    if not data_url:
        return None

    match = re.fullmatch(
        r"data:image/(png|jpeg);base64,([A-Za-z0-9+/=\s]+)",
        data_url,
    )
    if not match:
        raise ValueError("Screenshot must be a PNG or JPEG data URL")

    raw = base64.b64decode(match.group(2), validate=False)
    if len(raw) > MAX_SCREENSHOT_BYTES:
        raise ValueError("Screenshot exceeds the 5 MB limit")

    extension = "jpg" if match.group(1) == "jpeg" else "png"
    return raw, extension


def publish_layout_export(
    *,
    export_data: dict[str, Any],
    repository: str,
    branch: str,
    folder: str,
    token: str,
    screenshot: tuple[bytes, str] | None = None,
) -> dict[str, Any]:
    stamp = _utc_stamp()
    callsign = _slugify(
        export_data.get("author", {}).get("callsign", "n0call"),
        "n0call",
    )
    title = export_data.get("metadata", {}).get("title") or "dashboard-matrix-layout"
    basename = f"{stamp}-{callsign}-{_slugify(title)}"
    folder = _clean_folder(folder)
    owner_folder = f"{folder}/{callsign}"

    json_path = f"{owner_folder}/{basename}.json"
    json_bytes = json.dumps(
        export_data,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")

    json_result = _github_put_file(
        repository=repository,
        branch=branch,
        path=json_path,
        content=json_bytes,
        message=f"Add Dashboard Matrix layout export {basename}",
        token=token,
    )

    screenshot_result = None
    screenshot_path = None
    if screenshot:
        raw, extension = screenshot
        screenshot_path = f"{owner_folder}/{basename}.{extension}"
        screenshot_result = _github_put_file(
            repository=repository,
            branch=branch,
            path=screenshot_path,
            content=raw,
            message=f"Add Dashboard Matrix layout screenshot {basename}",
            token=token,
        )

    return {
        "repository": repository,
        "branch": branch,
        "json_path": json_path,
        "json_url": json_result.get("content", {}).get("html_url"),
        "screenshot_path": screenshot_path,
        "screenshot_url": (
            screenshot_result.get("content", {}).get("html_url")
            if screenshot_result
            else None
        ),
    }


@router.get("/current")
def current_layout_export(
    include_station: bool = Query(default=False),
    _: None = Depends(require_admin),
) -> dict[str, Any]:
    return build_layout_export(include_station=include_station)


@router.get("/download")
def download_layout_export(
    include_station: bool = Query(default=False),
    _: None = Depends(require_admin),
) -> Response:
    export_data = build_layout_export(include_station=include_station)
    callsign = _slugify(
        export_data["author"].get("callsign", "n0call"),
        "n0call",
    )
    filename = f"{_utc_stamp()}-{callsign}-dashboard-matrix-layout.json"
    body = json.dumps(export_data, indent=2, sort_keys=True)
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/publish-settings")
def read_publish_settings(
    _: None = Depends(require_admin),
) -> dict[str, Any]:
    defaults = {
        "repository": "KQ4DLB/dashboard-matrix-exchange",
        "branch": "main",
        "folder": "layouts",
    }
    with connection() as conn:
        station = get_station_settings(conn)
    result = {
        field: station.get(setting_key, defaults[field])
        for field, setting_key in PUBLISH_SETTING_KEYS.items()
    }
    result["auto_publish"] = station.get("layout_share_auto_publish", "0") == "1"
    return result


@router.put("/publish-settings")
def update_publish_settings(
    item: PublishSettingsUpdate,
    _: None = Depends(require_admin),
) -> dict[str, Any]:
    values = {
        PUBLISH_SETTING_KEYS["repository"]: item.repository,
        PUBLISH_SETTING_KEYS["branch"]: item.branch,
        PUBLISH_SETTING_KEYS["folder"]: _clean_folder(item.folder),
        "layout_share_auto_publish": "1" if item.auto_publish else "0",
    }

    with connection() as conn:
        for key, value in values.items():
            conn.execute(
                """
                INSERT INTO station_settings(key,value)
                VALUES(?,?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (key, value),
            )

    return {
        "repository": item.repository,
        "branch": item.branch,
        "folder": _clean_folder(item.folder),
        "auto_publish": item.auto_publish,
    }


@router.post("/publish")
def publish_current_layout(
    item: PublishRequest,
    _: None = Depends(require_admin),
) -> dict[str, Any]:
    token = item.token or os.getenv(TOKEN_ENV, "")
    if not token:
        raise HTTPException(
            400,
            f"GitHub token missing. Supply token or set {TOKEN_ENV}.",
        )

    metadata = item.metadata.model_dump()

    try:
        export_data = (
            _validated_publish_document(item.document)
            if item.document is not None
            else build_layout_export(
                include_station=item.include_station,
                metadata=metadata,
            )
        )
        screenshot = _decode_screenshot(item.screenshot_data_url)
        return publish_layout_export(
            export_data=export_data,
            repository=item.repository,
            branch=item.branch,
            folder=item.folder,
            token=token,
            screenshot=screenshot,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(502, str(exc)) from exc
