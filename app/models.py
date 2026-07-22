from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator

TileType = Literal["iframe", "image", "rotation", "text", "clock", "status", "provider", "script", "plugin"]

class DashboardBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    columns: int = Field(default=4, ge=1, le=12)
    rows: int = Field(default=3, ge=1, le=12)
    rotate_seconds: int = Field(default=0, ge=0, le=86400)
    is_default: bool = False
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)

class DashboardCreate(DashboardBase): pass
class DashboardUpdate(DashboardBase): pass

class TileBase(BaseModel):
    dashboard_id: int = 1
    title: str = Field(min_length=1, max_length=120)
    tile_type: TileType
    sources: list[str] = Field(default_factory=list)
    row_pos: int = Field(default=1, ge=1)
    col_pos: int = Field(default=1, ge=1)
    width: int = Field(default=1, ge=1, le=12)
    height: int = Field(default=1, ge=1, le=24)
    locked: bool = False
    refresh_seconds: int = Field(default=300, ge=0, le=86400)
    rotate_seconds: int = Field(default=0, ge=0, le=86400)
    enabled: bool = True
    settings: dict[str, Any] = Field(default_factory=dict)

    @field_validator("sources")
    @classmethod
    def strip_sources(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]

class TileCreate(TileBase): pass
class TileUpdate(TileBase): pass

class TilePosition(BaseModel):
    id: int
    row_pos: int = Field(ge=1)
    col_pos: int = Field(ge=1)
    width: int = Field(ge=1, le=12)
    height: int = Field(ge=1, le=24)
    locked: bool = False

class Tile(TileBase):
    id: int

class Dashboard(DashboardBase):
    id: int
    tiles: list[Tile] = Field(default_factory=list)

class StationSettings(BaseModel):
    callsign: str = Field(min_length=3, max_length=12, pattern=r"^[A-Za-z0-9/]+$")
    grid_square: str = Field(min_length=6, max_length=6, pattern=r"^[A-Ra-r]{2}[0-9]{2}[A-Xa-x]{2}$")

    @field_validator("callsign")
    @classmethod
    def normalize_callsign(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("grid_square")
    @classmethod
    def normalize_grid_square(cls, value: str) -> str:
        value = value.strip()
        return value[:2].upper() + value[2:4] + value[4:].lower()

class StationSettingsResponse(StationSettings):
    latitude: float
    longitude: float
    display_name: str = "Dashboard Matrix"
    default_theme: str = "matrix-dark"


class CatalogItemBase(BaseModel):
    item_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    category: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    tile_type: TileType
    sources: list[str] = Field(default_factory=list)
    refresh_seconds: int = Field(default=300, ge=0, le=86400)
    rotate_seconds: int = Field(default=0, ge=0, le=86400)
    settings: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)

    @field_validator("sources")
    @classmethod
    def strip_catalog_sources(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]

class CatalogItemCreate(CatalogItemBase): pass
class CatalogItemUpdate(CatalogItemBase): pass
class CatalogItem(CatalogItemBase): pass

class ProxySourceBase(BaseModel):
    source_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=8, max_length=500)
    enabled: bool = False
    strip_x_frame_options: bool = True
    strip_frame_ancestors: bool = True
    inject_base_tag: bool = True
    allow_http: bool = False
    cache_seconds: int = Field(default=0, ge=0, le=86400)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        from urllib.parse import urlsplit
        value = value.strip().rstrip("/") + "/"
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Base URL must be an absolute http:// or https:// URL")
        if parsed.username or parsed.password:
            raise ValueError("Credentials are not allowed in proxy base URLs")
        return value

class ProxySourceCreate(ProxySourceBase): pass
class ProxySourceUpdate(ProxySourceBase): pass
class ProxySource(ProxySourceBase): pass
