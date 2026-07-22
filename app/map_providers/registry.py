from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.map_providers.base import MapProvider

router = APIRouter(tags=["map-providers"])
_PROVIDERS: dict[str, MapProvider] = {}


def register_provider(provider: MapProvider) -> None:
    provider_id = provider.manifest.id
    if provider_id in _PROVIDERS:
        raise RuntimeError(f"Map provider already registered: {provider_id}")
    _PROVIDERS[provider_id] = provider


def get_provider(provider_id: str) -> MapProvider:
    provider = _PROVIDERS.get(provider_id)
    if provider is None:
        raise HTTPException(404, f"Map provider not found: {provider_id}")
    return provider


def list_providers() -> list[dict[str, Any]]:
    return [
        provider.manifest.public()
        | {"catalog_item": provider.catalog_item()}
        for provider in sorted(
            _PROVIDERS.values(),
            key=lambda value: value.manifest.name.lower(),
        )
    ]


@router.get("/api/map-providers")
def map_provider_index() -> list[dict[str, Any]]:
    return list_providers()
