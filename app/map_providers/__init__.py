from app.map_providers.dxcluster import provider as dxcluster_provider
from app.map_providers.registry import register_provider

register_provider(dxcluster_provider)

__all__ = ["dxcluster_provider"]
