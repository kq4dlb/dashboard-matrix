from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

from app.paths import data_dir
from app.version import DEFAULT_EXCHANGE_REPOSITORY, DEFAULT_UPDATE_REPOSITORY

DB_PATH = data_dir() / "dashboard-matrix.db"


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


@contextmanager
def catalog_connection() -> Iterator[sqlite3.Connection]:
    with connection() as conn:
        yield conn


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO station_settings(key,value) VALUES(?,?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        (key, value),
    )


def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute(
        "SELECT value FROM station_settings WHERE key=?",
        (key,),
    ).fetchone()
    return str(row[0]) if row else default


def is_setup_complete() -> bool:
    if not DB_PATH.exists():
        return False
    with connection() as conn:
        return get_setting(conn, "setup_complete", "0") == "1"


def init_db() -> None:
    db_existed = DB_PATH.exists()
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS dashboards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                columns INTEGER NOT NULL DEFAULT 4,
                rows INTEGER NOT NULL DEFAULT 3,
                rotate_seconds INTEGER NOT NULL DEFAULT 0,
                is_default INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS station_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS catalog_items (
                item_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                tile_type TEXT NOT NULL,
                sources_json TEXT NOT NULL DEFAULT '[]',
                refresh_seconds INTEGER NOT NULL DEFAULT 300,
                rotate_seconds INTEGER NOT NULL DEFAULT 0,
                settings_json TEXT NOT NULL DEFAULT '{}',
                enabled INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS proxy_sources (
                source_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                base_url TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0,
                strip_x_frame_options INTEGER NOT NULL DEFAULT 1,
                strip_frame_ancestors INTEGER NOT NULL DEFAULT 1,
                inject_base_tag INTEGER NOT NULL DEFAULT 1,
                allow_http INTEGER NOT NULL DEFAULT 0,
                cache_seconds INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS plugin_states (
                plugin_id TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 1,
                settings_json TEXT NOT NULL DEFAULT '{}',
                approvals_json TEXT NOT NULL DEFAULT '[]',
                secret_refs_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS marketplace_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                index_url TEXT NOT NULL UNIQUE,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_sync TEXT,
                last_error TEXT,
                cached_index_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS marketplace_installs (
                item_id TEXT PRIMARY KEY,
                source_id INTEGER,
                version TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                installed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(source_id) REFERENCES marketplace_sources(id)
                    ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS tiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dashboard_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                tile_type TEXT NOT NULL,
                sources_json TEXT NOT NULL DEFAULT '[]',
                row_pos INTEGER NOT NULL DEFAULT 1,
                col_pos INTEGER NOT NULL DEFAULT 1,
                width INTEGER NOT NULL DEFAULT 1,
                height INTEGER NOT NULL DEFAULT 1,
                locked INTEGER NOT NULL DEFAULT 0,
                refresh_seconds INTEGER NOT NULL DEFAULT 300,
                rotate_seconds INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                settings_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY(dashboard_id) REFERENCES dashboards(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS layout_import_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                source_name TEXT NOT NULL DEFAULT '',
                conflict_strategy TEXT NOT NULL,
                result_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS update_checks (
                id INTEGER PRIMARY KEY CHECK(id=1),
                checked_at TEXT,
                channel TEXT NOT NULL DEFAULT 'beta',
                current_version TEXT NOT NULL DEFAULT '',
                latest_version TEXT NOT NULL DEFAULT '',
                update_available INTEGER NOT NULL DEFAULT 0,
                release_url TEXT NOT NULL DEFAULT '',
                message TEXT NOT NULL DEFAULT ''
            );
            """
        )

        tile_columns = _columns(conn, "tiles")
        if "locked" not in tile_columns:
            conn.execute(
                "ALTER TABLE tiles ADD COLUMN locked INTEGER NOT NULL DEFAULT 0"
            )

        dashboard_columns = _columns(conn, "dashboards")
        if "enabled" not in dashboard_columns:
            conn.execute(
                "ALTER TABLE dashboards ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1"
            )
        if "sort_order" not in dashboard_columns:
            conn.execute(
                "ALTER TABLE dashboards ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0"
            )

        plugin_columns = _columns(conn, "plugin_states")
        if "approvals_json" not in plugin_columns:
            conn.execute(
                "ALTER TABLE plugin_states ADD COLUMN approvals_json TEXT NOT NULL DEFAULT '[]'"
            )
        if "secret_refs_json" not in plugin_columns:
            conn.execute(
                "ALTER TABLE plugin_states ADD COLUMN secret_refs_json TEXT NOT NULL DEFAULT '{}'"
            )

        defaults = {
            "callsign": "N0CALL",
            "grid_square": "AA00aa",
            "display_name": "Dashboard Matrix",
            "default_theme": "matrix-dark",
            "release_channel": "beta",
            "update_repository": DEFAULT_UPDATE_REPOSITORY,
            "layout_share_repository": DEFAULT_EXCHANGE_REPOSITORY,
            "layout_share_branch": "main",
            "layout_share_folder": "layouts",
            "layout_share_auto_publish": "0",
        }
        for key, value in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO station_settings(key,value) VALUES(?,?)",
                (key, value),
            )

        dashboard_count = conn.execute(
            "SELECT COUNT(*) FROM dashboards"
        ).fetchone()[0]
        if db_existed and dashboard_count > 0:
            set_setting(conn, "setup_complete", "1")
        else:
            conn.execute(
                "INSERT OR IGNORE INTO station_settings(key,value) VALUES('setup_complete','0')"
            )

        seed_catalog(conn)
        seed_proxy_sources(conn)
        conn.execute(
            """
            INSERT OR IGNORE INTO marketplace_sources(name,index_url,enabled)
            VALUES(?,?,0)
            """,
            (
                "Dashboard Matrix Exchange",
                "https://raw.githubusercontent.com/KQ4DLB/dashboard-matrix-exchange/main/index.json",
            ),
        )
        migrate_station_placeholders(conn)
        migrate_clock_to_titlebar(conn)


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    result = dict(row)
    for key in (
        "sources_json",
        "settings_json",
        "approvals_json",
        "secret_refs_json",
        "result_json",
    ):
        if key in result:
            target = key.removesuffix("_json")
            fallback: Any = [] if key in {"sources_json", "approvals_json"} else {}
            try:
                result[target] = json.loads(result.pop(key) or json.dumps(fallback))
            except json.JSONDecodeError:
                result[target] = fallback
    for key in (
        "enabled",
        "is_default",
        "locked",
        "strip_x_frame_options",
        "strip_frame_ancestors",
        "inject_base_tag",
        "allow_http",
        "update_available",
    ):
        if key in result:
            result[key] = bool(result[key])
    return result


def migrate_station_placeholders(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT id,sources_json FROM tiles").fetchall()
    for row in rows:
        try:
            sources = json.loads(row["sources_json"] or "[]")
        except json.JSONDecodeError:
            continue
        changed = False
        upgraded: list[str] = []
        for source in sources:
            if source == "https://www.pskreporter.info/pskmap.html":
                source = (
                    "https://www.pskreporter.info/pskmap.html#preset"
                    "&callsign={{CALLSIGN}}&mapCenter={{LAT}},{{LONG}},6.5"
                )
                changed = True
            elif (
                "pskreporter.info/pskmap.html" in source
                and "callsign={{CALLSIGN}}" in source
                and "mapCenter={{LAT}},{{LONG}}" not in source
            ):
                source = (
                    "https://www.pskreporter.info/pskmap.html#preset"
                    "&callsign={{CALLSIGN}}&mapCenter={{LAT}},{{LONG}},6.5"
                )
                changed = True
            upgraded.append(source)
        if changed:
            conn.execute(
                "UPDATE tiles SET sources_json=? WHERE id=?",
                (json.dumps(upgraded), row["id"]),
            )


def get_station_settings(conn: sqlite3.Connection) -> dict[str, str]:
    return {
        row["key"]: row["value"]
        for row in conn.execute(
            "SELECT key,value FROM station_settings"
        ).fetchall()
    }


def maidenhead_center(grid_square: str) -> tuple[float, float]:
    grid = grid_square.strip()
    if len(grid) != 6:
        raise ValueError("Grid square must contain exactly six characters")
    upper = grid.upper()
    if not (
        "A" <= upper[0] <= "R"
        and "A" <= upper[1] <= "R"
        and upper[2:4].isdigit()
        and "A" <= upper[4] <= "X"
        and "A" <= upper[5] <= "X"
    ):
        raise ValueError("Invalid six-character Maidenhead grid square")
    longitude = (
        -180.0
        + (ord(upper[0]) - ord("A")) * 20.0
        + int(upper[2]) * 2.0
        + (ord(upper[4]) - ord("A")) * (5.0 / 60.0)
        + (2.5 / 60.0)
    )
    latitude = (
        -90.0
        + (ord(upper[1]) - ord("A")) * 10.0
        + int(upper[3])
        + (ord(upper[5]) - ord("A")) * (2.5 / 60.0)
        + (1.25 / 60.0)
    )
    return round(latitude, 6), round(longitude, 6)


def station_context(settings: dict[str, str]) -> dict[str, str]:
    callsign = settings.get("callsign", "N0CALL").upper()
    grid_square = settings.get("grid_square", "AA00aa")
    latitude, longitude = maidenhead_center(grid_square)
    return {
        "CALLSIGN": callsign,
        "callsign": callsign.lower(),
        "GRIDSQUARE": grid_square,
        "GRID_SQUARE": grid_square,
        "gridsquare": grid_square.lower(),
        "grid_square": grid_square.lower(),
        "LAT": str(latitude),
        "lat": str(latitude),
        "LATITUDE": str(latitude),
        "latitude": str(latitude),
        "LONG": str(longitude),
        "long": str(longitude),
        "LON": str(longitude),
        "lon": str(longitude),
        "LONGITUDE": str(longitude),
        "longitude": str(longitude),
    }


def apply_station_placeholders(value: str, settings: dict[str, str]) -> str:
    result = value
    context = station_context(settings)
    for key, raw_value in context.items():
        result = result.replace("{{" + key + "}}", raw_value)
    if result.lower().startswith("nws-radar://"):
        try:
            from app.nws_radar import resolve_radar_source

            result = resolve_radar_source(
                result,
                float(context["LAT"]),
                float(context["LONG"]),
            )
        except Exception:
            result = "https://radar.weather.gov/"
    if result.startswith("proxy://"):
        proxy_value = result[len("proxy://") :]
        source_id, separator, remainder = proxy_value.partition("/")
        result = (
            f"/proxy/{source_id}/" + remainder
            if separator
            else f"/proxy/{source_id}/"
        )
    return result


def migrate_clock_to_titlebar(conn: sqlite3.Connection) -> None:
    conn.execute(
        "DELETE FROM tiles WHERE tile_type='clock' AND title IN ('Local Time','Clock')"
    )


def seed_catalog(conn: sqlite3.Connection) -> None:
    from app.catalog import CATALOG

    for index, item in enumerate(CATALOG):
        conn.execute(
            """
            INSERT OR IGNORE INTO catalog_items(
                item_id,category,title,description,tile_type,sources_json,
                refresh_seconds,rotate_seconds,settings_json,enabled,sort_order
            ) VALUES(?,?,?,?,?,?,?,?,?,1,?)
            """,
            (
                item["id"],
                item["category"],
                item["title"],
                item.get("description", ""),
                item["tile_type"],
                json.dumps(item.get("sources", [])),
                item.get("refresh_seconds", 300),
                item.get("rotate_seconds", 0),
                json.dumps(item.get("settings", {})),
                index,
            ),
        )


def seed_proxy_sources(conn: sqlite3.Connection) -> None:
    examples = [
        ("blitzortung", "Blitzortung", "https://map.blitzortung.org/"),
        ("psk-reporter", "PSK Reporter", "https://www.pskreporter.info/"),
        ("qrz", "QRZ", "https://www.qrz.com/"),
    ]
    for source_id, name, base_url in examples:
        conn.execute(
            """
            INSERT OR IGNORE INTO proxy_sources(
                source_id,name,base_url,enabled,strip_x_frame_options,
                strip_frame_ancestors,inject_base_tag,allow_http,cache_seconds
            ) VALUES(?,?,?,0,1,1,1,0,0)
            """,
            (source_id, name, base_url),
        )
