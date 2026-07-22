# Map Provider SDK

Map support is split into three layers:

1. `app/map_providers/profiles.py` owns reusable center, zoom, bounds, radius, and station-location profiles.
2. `app/map_providers/registry.py` discovers registered providers and exposes `/api/map-providers`.
3. Each provider owns its upstream integration and routes. The bundled HA8TKS adapter lives in `app/map_providers/dxcluster.py`.

A provider supplies a `MapProviderManifest`, an `APIRouter`, and a catalog item:

```python
from fastapi import APIRouter
from app.map_providers.base import MapProviderManifest

class ExampleProvider:
    manifest = MapProviderManifest(
        id="example",
        name="Example Map",
        version="1.0.0",
        description="Example provider",
        capabilities=("markers", "layers"),
    )
    router = APIRouter()

    @staticmethod
    def catalog_item():
        return {
            "item_id": "example-map",
            "category": "Maps",
            "title": "Example Map",
            "tile_type": "iframe",
            "sources": ["/maps/example"],
            "settings": {"map_provider": "example"},
            "refresh_seconds": 60,
            "rotate_seconds": 0
        }
```

Register the instance in `app/map_providers/__init__.py`. Provider-specific
proxying, credentials, data normalization, marker formats, and layer controls
remain outside the common profile engine.
