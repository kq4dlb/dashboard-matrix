from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.paths import ROOT_DIR, user_themes_dir

router = APIRouter(tags=["themes"])
THEME_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
BUNDLED_THEME_DIR = ROOT_DIR / "themes"


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
                manifest.setdefault("color_scheme", "dark")
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


def _raise_theme(theme_id: str):
    raise HTTPException(404, f"Theme not found: {theme_id}")


@router.get("/api/themes")
def list_themes() -> list[dict[str, Any]]:
    return [
        {key: value for key, value in theme.items() if not key.startswith("_")}
        | {"stylesheet_url": f"/themes/{theme['id']}.css"}
        for theme in discover_themes()
    ]


@router.get("/themes/{theme_id}.css")
def theme_stylesheet(theme_id: str) -> Response:
    theme = get_theme(theme_id)
    css = Path(theme["_css"]).read_text(encoding="utf-8")
    return Response(
        css,
        media_type="text/css",
        headers={"Cache-Control": "public, max-age=300"},
    )
