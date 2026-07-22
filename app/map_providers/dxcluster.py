from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response

from app.auth import require_admin
from app.database import catalog_connection, connection
from app.map_providers.base import MapProviderManifest
from app.map_providers.profiles import profile_payload

DX_CLUSTER_ORIGIN = "https://dxcluster.ha8tks.hu"
DX_CLUSTER_PATH = "/map/"
DX_CLUSTER_URL = f"{DX_CLUSTER_ORIGIN}{DX_CLUSTER_PATH}"
DX_PROXY_PREFIX = "/maps/dxcluster/upstream"


class DXClusterProvider:
    manifest = MapProviderManifest(
        id="dxcluster",
        name="HA8TKS DX Cluster Map",
        version="0.1.0",
        description="Adapts the HA8TKS DX Cluster map to Dashboard Matrix map profiles.",
        author="Dashboard Matrix Project",
        capabilities=("embedded-map", "profile-center", "profile-bounds", "upstream-proxy"),
        configuration_schema={
            "type": "object",
            "properties": {
                "profile": {"type": "string"},
            },
        },
    )
    router = APIRouter(tags=["map-provider-dxcluster"])

    @staticmethod
    def catalog_item() -> dict[str, Any]:
        return {
            "item_id": "dx-cluster-map-adapted",
            "category": "DX & Propagation",
            "title": "DX Cluster Map — Dashboard Matrix View",
            "description": "HA8TKS DX Cluster map using the selected Dashboard Matrix map profile.",
            "tile_type": "iframe",
            "sources": ["/maps/dxcluster"],
            "refresh_seconds": 60,
            "rotate_seconds": 0,
            "settings": {"map_provider": "dxcluster"},
        }


def _adapter_script(profile: dict[str, Any]) -> str:
    payload = json.dumps(profile, separators=(",", ":")).replace("</", "<\\/")
    return f"""
<script>
(() => {{
  const profile = {payload};
  const targetCenter = [profile.center_lat, profile.center_lon];
  const targetBounds = profile.bounds;
  let completed = false;
  let capturedMap = null;

  function isMapCandidate(value) {{
    return value && typeof value === "object" && (
      typeof value.setView === "function" ||
      typeof value.fitBounds === "function" ||
      typeof value.jumpTo === "function" ||
      typeof value.getView === "function"
    );
  }}

  function wrapLeaflet() {{
    if (!window.L || window.L.__dashboardMatrixWrapped || typeof window.L.map !== "function") return;
    const original = window.L.map.bind(window.L);
    window.L.map = function(...args) {{
      const map = original(...args);
      capturedMap = map;
      setTimeout(() => applyTo(map), 0);
      return map;
    }};
    window.L.__dashboardMatrixWrapped = true;
  }}

  function findCandidate() {{
    if (capturedMap) return capturedMap;
    for (const candidate of [window.map, window.mymap, window.mainMap, window.dxMap, window.olMap, window.maplibreMap]) {{
      if (isMapCandidate(candidate)) return candidate;
    }}
    for (const key of Object.keys(window)) {{
      let value;
      try {{ value = window[key]; }} catch {{ continue; }}
      if (isMapCandidate(value)) return value;
    }}
    return null;
  }}

  function applyTo(map) {{
    try {{
      if (targetBounds && typeof map.fitBounds === "function") {{
        map.fitBounds(targetBounds, {{animate:false,padding:[4,4]}});
        completed = true;
      }} else if (typeof map.setView === "function") {{
        map.setView(targetCenter, profile.zoom, {{animate:false}});
        completed = true;
      }} else if (typeof map.jumpTo === "function") {{
        map.jumpTo({{center:[profile.center_lon,profile.center_lat],zoom:profile.zoom}});
        completed = true;
      }} else if (typeof map.getView === "function") {{
        const view = map.getView();
        if (view && typeof view.setCenter === "function") {{
          if (window.ol?.proj?.fromLonLat) view.setCenter(window.ol.proj.fromLonLat([profile.center_lon, profile.center_lat]));
          if (typeof view.setZoom === "function") view.setZoom(profile.zoom);
          completed = true;
        }}
      }}
    }} catch (error) {{ console.debug("Dashboard Matrix map provider retry", error); }}
  }}

  let attempts = 0;
  const timer = setInterval(() => {{
    attempts += 1;
    wrapLeaflet();
    const map = findCandidate();
    if (map) applyTo(map);
    if (completed || attempts > 600) clearInterval(timer);
  }}, 100);
  window.__DASHBOARD_MATRIX_MAP_PROFILE__ = profile;
}})();
</script>
"""


def _rewrite_root_relative(text: str) -> str:
    text = re.sub(
        r'(["\'])/(?!/)',
        lambda match: f'{match.group(1)}{DX_PROXY_PREFIX}/',
        text,
    )
    return re.sub(
        r"url\(\s*/(?!/)",
        f"url({DX_PROXY_PREFIX}/",
        text,
        flags=re.IGNORECASE,
    )


def _inject_html(document: str, profile: dict[str, Any]) -> str:
    document = _rewrite_root_relative(document)
    injection = f'<base href="{DX_PROXY_PREFIX}/map/">' + _adapter_script(profile)
    head = re.search(r"<head[^>]*>", document, flags=re.IGNORECASE)
    return (
        document[: head.end()] + injection + document[head.end() :]
        if head
        else injection + document
    )


def _forward_headers(request: Request) -> dict[str, str]:
    headers = {
        "User-Agent": "Dashboard-Matrix/DX-Map-Provider (kq4dlb@kq4dlb.com)",
        "Accept": request.headers.get("accept", "*/*"),
        "Accept-Language": request.headers.get("accept-language", "en-US,en;q=0.8"),
        "Accept-Encoding": "identity",
        "Referer": DX_CLUSTER_URL,
    }
    for incoming, outgoing in (
        ("if-none-match", "If-None-Match"),
        ("if-modified-since", "If-Modified-Since"),
    ):
        if request.headers.get(incoming):
            headers[outgoing] = request.headers[incoming]
    return headers


def _safe_response_headers(response: httpx.Response) -> dict[str, str]:
    excluded = {
        "content-length", "content-encoding", "transfer-encoding", "connection",
        "set-cookie", "x-frame-options", "content-security-policy",
        "content-security-policy-report-only",
    }
    headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in excluded
    }
    headers["X-Dashboard-Matrix-Proxied-Origin"] = DX_CLUSTER_ORIGIN
    return headers


async def _fetch_upstream(request: Request, upstream_url: str) -> httpx.Response:
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
        ) as client:
            return await client.request(
                request.method,
                upstream_url,
                params=request.query_params,
                headers=_forward_headers(request),
            )
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Unable to load DX Cluster resource: {exc}") from exc


@DXClusterProvider.router.api_route(
    "/maps/dxcluster/upstream/{resource_path:path}",
    methods=["GET", "HEAD"],
)
async def dxcluster_upstream(request: Request, resource_path: str) -> Response:
    upstream_url = urljoin(f"{DX_CLUSTER_ORIGIN}/", resource_path.lstrip("/"))
    response = await _fetch_upstream(request, upstream_url)
    content_type = response.headers.get("content-type", "").lower()
    body = response.content
    if request.method != "HEAD" and any(
        value in content_type
        for value in ("text/html", "text/css", "javascript", "application/json", "text/plain")
    ):
        try:
            body = _rewrite_root_relative(response.text).encode(response.encoding or "utf-8")
        except (UnicodeDecodeError, LookupError):
            body = response.content
    return Response(
        content=body if request.method != "HEAD" else b"",
        status_code=response.status_code,
        headers=_safe_response_headers(response),
        media_type=response.headers.get("content-type"),
    )


@DXClusterProvider.router.get("/maps/dxcluster", response_class=HTMLResponse)
async def dxcluster_map(request: Request, profile: str | None = Query(default=None)) -> HTMLResponse:
    selected = profile_payload(profile)
    response = await _fetch_upstream(request, DX_CLUSTER_URL)
    if response.status_code >= 400:
        raise HTTPException(response.status_code, "DX Cluster returned an error")
    if "text/html" not in response.headers.get("content-type", "").lower():
        raise HTTPException(502, "DX Cluster returned a non-HTML response")
    return HTMLResponse(
        _inject_html(response.text, selected),
        headers={
            "Cache-Control": "no-store",
            "X-Dashboard-Matrix-Map-Profile": selected["profile"],
        },
    )


@DXClusterProvider.router.get("/map-adapter/dxcluster", include_in_schema=False)
async def legacy_dxcluster_alias(request: Request, profile: str | None = Query(default=None)) -> HTMLResponse:
    return await dxcluster_map(request, profile)


@DXClusterProvider.router.api_route(
    "/map-adapter/dxcluster/upstream/{resource_path:path}",
    methods=["GET", "HEAD"],
    include_in_schema=False,
)
async def legacy_dxcluster_upstream(request: Request, resource_path: str) -> Response:
    return await dxcluster_upstream(request, resource_path)


@DXClusterProvider.router.post("/api/map-providers/dxcluster/install-catalog")
def install_catalog(_: None = Depends(require_admin)) -> dict[str, Any]:
    item = DXClusterProvider.catalog_item()
    with catalog_connection() as conn:
        conn.execute(
            """
            INSERT INTO catalog_items(
                item_id,category,title,description,tile_type,sources_json,
                refresh_seconds,rotate_seconds,settings_json,enabled,sort_order
            ) VALUES(?,?,?,?,?,?,?,?,?,1,120)
            ON CONFLICT(item_id) DO UPDATE SET
                category=excluded.category,title=excluded.title,
                description=excluded.description,tile_type=excluded.tile_type,
                sources_json=excluded.sources_json,
                refresh_seconds=excluded.refresh_seconds,
                rotate_seconds=excluded.rotate_seconds,
                settings_json=excluded.settings_json,enabled=1
            """,
            (
                item["item_id"], item["category"], item["title"], item["description"],
                item["tile_type"], json.dumps(item["sources"]),
                item["refresh_seconds"], item["rotate_seconds"],
                json.dumps(item["settings"]),
            ),
        )
    updated = 0
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id,title,sources_json FROM tiles
            WHERE lower(title) LIKE '%dx%cluster%'
               OR sources_json LIKE '%dxcluster.ha8tks.hu/map%'
               OR sources_json LIKE '%/map-adapter/dxcluster%'
            """
        ).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE tiles SET tile_type='iframe',sources_json=?,settings_json=? WHERE id=?",
                (json.dumps(["/maps/dxcluster"]), json.dumps({"map_provider":"dxcluster"}), row["id"]),
            )
            updated += 1
    return {"status": "installed", "item_id": item["item_id"], "tiles_updated": updated}


provider = DXClusterProvider()
