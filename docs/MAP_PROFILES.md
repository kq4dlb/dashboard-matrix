# Dashboard Matrix Map View Profiles

## Purpose

Map View Profiles provide one shared map center, zoom, bounds, and distance
radius for map-based tiles.

The initial release includes:

- Worldwide
- North America
- Continental United States
- Eastern United States
- Central United States
- Western United States
- Southeast United States
- Northeast United States
- Southwest United States
- Pacific Northwest
- Local station area
- Custom center

## DX Cluster adapter

The catalog installer creates:

```text
DX Cluster Map — Dashboard Matrix View
```

Its tile source is:

```text
/map-adapter/dxcluster
```

The route retrieves the HA8TKS page server-side, inserts a base tag, and injects
a small adapter that attempts Leaflet, MapLibre/Mapbox, and OpenLayers APIs.

Because HA8TKS does not publish a supported viewport API, this integration is
best-effort. If the site changes its internal map implementation, the adapter
may require an update.

A tile can override the global profile:

```text
/map-adapter/dxcluster?profile=continental-us
/map-adapter/dxcluster?profile=southeast-us
/map-adapter/dxcluster?profile=local
```
