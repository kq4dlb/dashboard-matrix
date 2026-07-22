from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from typing import Any

STARTER_TEMPLATES: dict[str, dict[str, Any]] = {
    "blank": {
        "name": "Blank",
        "description": "One empty dashboard ready for your own cards.",
        "dashboards": [
            {
                "name": "Dashboard",
                "slug": "main",
                "columns": 4,
                "rows": 3,
                "rotate_seconds": 0,
                "is_default": True,
                "tiles": [],
            }
        ],
    },
    "amateur-radio": {
        "name": "Amateur Radio",
        "description": "Station identity, weather, radar, DX mapping, propagation, and space weather.",
        "dashboards": [
            {
                "name": "Radio Dashboard",
                "slug": "main",
                "columns": 4,
                "rows": 3,
                "rotate_seconds": 45,
                "is_default": True,
                "tiles": [
                    {
                        "title": "Station Identity",
                        "tile_type": "plugin",
                        "row_pos": 1,
                        "col_pos": 1,
                        "width": 1,
                        "height": 1,
                        "refresh_seconds": 60,
                        "settings": {
                            "plugin": "station-tools",
                            "widget": "station-card",
                            "settings": {},
                        },
                    },
                    {
                        "title": "Local Weather",
                        "tile_type": "provider",
                        "row_pos": 1,
                        "col_pos": 2,
                        "width": 2,
                        "height": 1,
                        "refresh_seconds": 600,
                        "settings": {
                            "provider": "nws_forecast",
                            "use_station_location": True,
                            "periods": 4,
                        },
                    },
                    {
                        "title": "NOAA Radar",
                        "tile_type": "iframe",
                        "sources": ["nws-radar://auto?zoom=8&animate=true"],
                        "row_pos": 1,
                        "col_pos": 4,
                        "width": 1,
                        "height": 2,
                        "refresh_seconds": 300,
                    },
                    {
                        "title": "DX and Propagation",
                        "tile_type": "rotation",
                        "sources": [
                            "https://www.pskreporter.info/pskmap.html#preset&callsign={{CALLSIGN}}&mapCenter={{LAT}},{{LONG}},6.5",
                            "/maps/dxcluster",
                        ],
                        "row_pos": 2,
                        "col_pos": 1,
                        "width": 2,
                        "height": 2,
                        "refresh_seconds": 300,
                        "rotate_seconds": 90,
                    },
                    {
                        "title": "System Status",
                        "tile_type": "status",
                        "row_pos": 2,
                        "col_pos": 3,
                        "width": 1,
                        "height": 1,
                        "refresh_seconds": 10,
                    },
                    {
                        "title": "Station Notes",
                        "tile_type": "text",
                        "sources": [
                            "Dashboard Matrix 0.1 beta — use Layout mode to move, resize, lock, and save cards."
                        ],
                        "row_pos": 3,
                        "col_pos": 3,
                        "width": 1,
                        "height": 1,
                        "refresh_seconds": 0,
                    },
                ],
            },
            {
                "name": "Space Weather",
                "slug": "space-weather",
                "columns": 3,
                "rows": 2,
                "rotate_seconds": 45,
                "is_default": False,
                "tiles": [
                    {
                        "title": "NOAA Space Weather Scales",
                        "tile_type": "provider",
                        "row_pos": 1,
                        "col_pos": 1,
                        "width": 1,
                        "height": 1,
                        "refresh_seconds": 300,
                        "settings": {"provider": "swpc_scales"},
                    },
                    {
                        "title": "Planetary K Index",
                        "tile_type": "provider",
                        "row_pos": 1,
                        "col_pos": 2,
                        "width": 2,
                        "height": 1,
                        "refresh_seconds": 300,
                        "settings": {"provider": "swpc_k_index"},
                    },
                    {
                        "title": "Solar Conditions",
                        "tile_type": "image",
                        "sources": ["https://www.hamqsl.com/solar101vhf.php"],
                        "row_pos": 2,
                        "col_pos": 1,
                        "width": 1,
                        "height": 1,
                        "refresh_seconds": 300,
                    },
                    {
                        "title": "SWPC Dashboard",
                        "tile_type": "iframe",
                        "sources": ["https://www.spaceweather.gov/"],
                        "row_pos": 2,
                        "col_pos": 2,
                        "width": 2,
                        "height": 1,
                        "refresh_seconds": 600,
                    },
                ],
            },
        ],
    },
    "home-lab": {
        "name": "Home Lab",
        "description": "A practical starting grid for infrastructure, monitoring, DNS, virtualization, and notes.",
        "dashboards": [
            {
                "name": "Home Lab",
                "slug": "main",
                "columns": 4,
                "rows": 3,
                "rotate_seconds": 0,
                "is_default": True,
                "tiles": [
                    {
                        "title": "System Status",
                        "tile_type": "status",
                        "row_pos": 1,
                        "col_pos": 1,
                        "width": 1,
                        "height": 1,
                        "refresh_seconds": 10,
                    },
                    {
                        "title": "Uptime Kuma",
                        "tile_type": "iframe",
                        "sources": ["http://uptime-kuma.local/status/default"],
                        "row_pos": 1,
                        "col_pos": 2,
                        "width": 2,
                        "height": 1,
                        "refresh_seconds": 60,
                    },
                    {
                        "title": "Pi-hole",
                        "tile_type": "iframe",
                        "sources": ["http://pi.hole/admin/"],
                        "row_pos": 1,
                        "col_pos": 4,
                        "width": 1,
                        "height": 1,
                        "refresh_seconds": 120,
                    },
                    {
                        "title": "Grafana",
                        "tile_type": "iframe",
                        "sources": ["http://grafana.local/"],
                        "row_pos": 2,
                        "col_pos": 1,
                        "width": 2,
                        "height": 2,
                        "refresh_seconds": 60,
                    },
                    {
                        "title": "Proxmox",
                        "tile_type": "iframe",
                        "sources": ["https://proxmox.local:8006/"],
                        "row_pos": 2,
                        "col_pos": 3,
                        "width": 2,
                        "height": 1,
                        "refresh_seconds": 60,
                    },
                    {
                        "title": "Lab Notes",
                        "tile_type": "text",
                        "sources": [
                            "Replace the sample .local addresses with your own services. Use a controlled proxy source only when you are authorized to proxy the destination."
                        ],
                        "row_pos": 3,
                        "col_pos": 3,
                        "width": 2,
                        "height": 1,
                        "refresh_seconds": 0,
                    },
                ],
            }
        ],
    },
}


def template_summaries() -> list[dict[str, str]]:
    return [
        {"id": key, "name": value["name"], "description": value["description"]}
        for key, value in STARTER_TEMPLATES.items()
    ]


def install_template(
    conn: sqlite3.Connection,
    template_id: str,
    *,
    replace_existing: bool = True,
) -> list[int]:
    template = deepcopy(STARTER_TEMPLATES.get(template_id) or STARTER_TEMPLATES["blank"])
    if replace_existing:
        conn.execute("DELETE FROM tiles")
        conn.execute("DELETE FROM dashboards")

    dashboard_ids: list[int] = []
    for sort_order, dashboard in enumerate(template["dashboards"]):
        dashboard_id = conn.execute(
            """
            INSERT INTO dashboards(
                name,slug,columns,rows,rotate_seconds,is_default,enabled,sort_order
            ) VALUES(?,?,?,?,?,?,1,?)
            """,
            (
                dashboard["name"],
                dashboard["slug"],
                dashboard.get("columns", 4),
                dashboard.get("rows", 3),
                dashboard.get("rotate_seconds", 0),
                int(dashboard.get("is_default", sort_order == 0)),
                sort_order,
            ),
        ).lastrowid
        dashboard_ids.append(int(dashboard_id))
        for tile in dashboard.get("tiles", []):
            conn.execute(
                """
                INSERT INTO tiles(
                    dashboard_id,title,tile_type,sources_json,row_pos,col_pos,
                    width,height,locked,refresh_seconds,rotate_seconds,enabled,
                    settings_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    dashboard_id,
                    tile["title"],
                    tile["tile_type"],
                    json.dumps(tile.get("sources", [])),
                    tile.get("row_pos", 1),
                    tile.get("col_pos", 1),
                    tile.get("width", 1),
                    tile.get("height", 1),
                    int(tile.get("locked", False)),
                    tile.get("refresh_seconds", 300),
                    tile.get("rotate_seconds", 0),
                    int(tile.get("enabled", True)),
                    json.dumps(tile.get("settings", {})),
                ),
            )
    return dashboard_ids
