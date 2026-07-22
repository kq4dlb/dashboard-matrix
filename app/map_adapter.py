"""Map-provider router and compatibility exports.

New providers should implement `app.map_providers.base.MapProvider`, register in
`app.map_providers.registry`, and expose their own APIRouter.
"""

from fastapi import APIRouter

from app.map_providers import dxcluster_provider
from app.map_providers.dxcluster import _rewrite_root_relative
from app.map_providers.profiles import PRESETS, profile_payload, router as profile_router
from app.map_providers.registry import router as registry_router

router = APIRouter()
router.include_router(profile_router)
router.include_router(registry_router)
router.include_router(dxcluster_provider.router)

__all__ = ["PRESETS", "profile_payload", "_rewrite_root_relative", "router"]
