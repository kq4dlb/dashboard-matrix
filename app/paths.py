from __future__ import annotations

import os
import sys
from pathlib import Path


def _resource_root() -> Path:
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle).resolve()
    return Path(__file__).resolve().parent.parent


ROOT_DIR = _resource_root()


def _configured_path(name: str, fallback: Path) -> Path:
    value = os.getenv(name)
    return Path(value).expanduser().resolve() if value else fallback.resolve()


def _persistent_root() -> Path:
    if getattr(sys, "frozen", False) or not (ROOT_DIR / "pyproject.toml").exists():
        if os.name == "nt":
            base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            return base / "DashboardMatrix"
        return Path.home() / ".local" / "share" / "dashboard-matrix"
    return ROOT_DIR


def data_dir() -> Path:
    return _configured_path(
        "DASHBOARD_MATRIX_DATA_DIR",
        _persistent_root() / "data",
    )


def user_plugins_dir() -> Path:
    return _configured_path(
        "DASHBOARD_MATRIX_USER_PLUGINS_DIR",
        _persistent_root() / "user_plugins",
    )


def user_scripts_dir() -> Path:
    return _configured_path(
        "DASHBOARD_MATRIX_USER_SCRIPTS_DIR",
        _persistent_root() / "user_scripts",
    )


def user_themes_dir() -> Path:
    return _configured_path(
        "DASHBOARD_MATRIX_USER_THEMES_DIR",
        _persistent_root() / "user_themes",
    )


def templates_dir() -> Path:
    return ROOT_DIR / "app" / "templates"


def static_dir() -> Path:
    return ROOT_DIR / "app" / "static"
