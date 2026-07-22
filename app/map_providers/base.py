from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from fastapi import APIRouter


@dataclass(frozen=True)
class MapProviderManifest:
    id: str
    name: str
    version: str
    description: str
    author: str = "Unknown"
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    configuration_schema: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["capabilities"] = list(self.capabilities)
        return payload


class MapProvider(Protocol):
    manifest: MapProviderManifest
    router: APIRouter

    def catalog_item(self) -> dict[str, Any]: ...
