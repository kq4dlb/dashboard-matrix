from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auth import require_admin
from app.database import connection, get_setting, set_setting
from app.paths import ROOT_DIR, user_themes_dir
from app.websocket import manager

router = APIRouter(tags=["themes"])
THEME_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
BUNDLED_THEME_DIR = ROOT_DIR / "themes"
DEFAULT_THEME_ID = "matrix-light"


class DefaultThemeUpdate(BaseModel):
    theme_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$", max_length=80)


def _theme_dirs() -> list[Path]:
    return [BUNDLED_THEME_DIR, user_themes_dir()]


def discover_themes() -> list[dict[str, Any]]:
    discovered: dict[str, dict[str, Any]] = {}
    for base in _theme_dirs():
        base.mkdir(parents=True, exist_ok=True)
        for manifest_path in sorted(base.glob("*/manifest.json")):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                theme_id = str(manifest.get("id", ""))
                if not THEME_ID.fullmatch(theme_id):
                    continue
                css_path = manifest_path.parent / str(
                    manifest.get("stylesheet", "theme.css")
                )
                if not css_path.exists():
                    continue
                manifest.setdefault("name", theme_id)
                manifest.setdefault("version", "0.0.0")
                manifest.setdefault("author", "Unknown")
                manifest.setdefault("description", "")
                manifest.setdefault("color_scheme", "light")
                manifest["_path"] = str(manifest_path.parent)
                manifest["_css"] = str(css_path)
                discovered[theme_id] = manifest
            except (OSError, ValueError, TypeError):
                continue
    return sorted(
        discovered.values(),
        key=lambda item: str(item.get("name", item["id"])).lower(),
    )


def get_theme(theme_id: str) -> dict[str, Any]:
    return next(
        (theme for theme in discover_themes() if theme["id"] == theme_id),
        None,
    ) or _raise_theme(theme_id)


def get_default_theme_id() -> str:
    with connection() as conn:
        configured = get_setting(conn, "default_theme", DEFAULT_THEME_ID)
    try:
        get_theme(configured)
        return configured
    except HTTPException:
        return DEFAULT_THEME_ID


def _raise_theme(theme_id: str):
    raise HTTPException(404, f"Theme not found: {theme_id}")


@router.get("/api/themes")
def list_themes() -> list[dict[str, Any]]:
    default_theme = get_default_theme_id()
    return [
        {key: value for key, value in theme.items() if not key.startswith("_")}
        | {
            "stylesheet_url": f"/themes/{theme['id']}.css",
            "is_default": theme["id"] == default_theme,
        }
        for theme in discover_themes()
    ]


@router.put("/api/themes/default")
async def update_default_theme(
    item: DefaultThemeUpdate,
    _: None = Depends(require_admin),
) -> dict[str, str]:
    theme = get_theme(item.theme_id)
    with connection() as conn:
        set_setting(conn, "default_theme", theme["id"])
    await manager.broadcast({"event": "configuration_changed"})
    return {
        "default_theme": theme["id"],
        "name": str(theme.get("name", theme["id"])),
    }


@router.get("/themes/{theme_id}.css")
def theme_stylesheet(theme_id: str) -> Response:
    theme = get_theme(theme_id)
    css = Path(theme["_css"]).read_text(encoding="utf-8")
    return Response(
        css,
        media_type="text/css",
        headers={"Cache-Control": "public, max-age=300"},
    )
