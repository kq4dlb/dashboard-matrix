from __future__ import annotations

import json, platform, shutil, time
from datetime import datetime, timezone
from pathlib import Path
from app.paths import data_dir, user_plugins_dir
from fastapi import APIRouter, Depends, HTTPException
from app.database import apply_station_placeholders, connection, get_station_settings, maidenhead_center, row_to_dict, station_context
from app.auth import change_password, require_admin
from app.models import CatalogItem, CatalogItemCreate, CatalogItemUpdate, Dashboard, DashboardCreate, DashboardUpdate, ProxySource, ProxySourceCreate, ProxySourceUpdate, StationSettings, StationSettingsResponse, Tile, TileCreate, TilePosition, TileUpdate
from app.providers.noaa import fetch_provider
from app.script_runner import available_scripts, run_script
from app.plugin_manager import discover_plugins, get_plugin, public_plugin, run_plugin_widget
from app.marketplace import MarketplaceError, fetch_index, install_plugin, uninstall_plugin
from app.websocket import manager
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api")
STARTED_AT = time.time()

class PasswordChange(BaseModel):
    password: str = Field(min_length=8, max_length=128)

def _dashboard(slug: str, include_disabled: bool = False) -> dict:
    with connection() as conn:
        row = conn.execute("SELECT * FROM dashboards WHERE slug=?", (slug,)).fetchone()
        if row is None: raise HTTPException(404, "Dashboard not found")
        result = row_to_dict(row)
        sql = "SELECT * FROM tiles WHERE dashboard_id=?"
        if not include_disabled: sql += " AND enabled=1"
        sql += " ORDER BY row_pos,col_pos,id"
        settings = get_station_settings(conn)
        result["tiles"] = [row_to_dict(r) for r in conn.execute(sql, (result["id"],)).fetchall()]
        for tile in result["tiles"]:
            tile["sources"] = [apply_station_placeholders(source, settings) for source in tile.get("sources", [])]
        return result


@router.get("/data-sources/hamqsl")
def hamqsl_source_status() -> dict:
    status_file = data_dir() / "hamqsl_status.json"
    cache_file = data_dir() / "hamqsl_solar.xml"
    status: dict = {"ok": False, "cache_available": cache_file.exists()}
    if status_file.exists():
        try:
            status.update(json.loads(status_file.read_text(encoding="utf-8")))
        except Exception as exc:
            status["error"] = f"Unable to read collector status: {exc}"
    if cache_file.exists():
        status["cache_age_seconds"] = max(0, int(time.time() - cache_file.stat().st_mtime))
        status["cache_bytes"] = cache_file.stat().st_size
    return status

@router.get("/settings/station", response_model=StationSettingsResponse)
def read_station_settings() -> dict:
    with connection() as conn:
        settings = get_station_settings(conn)
    grid_square = settings.get("grid_square", "AA00aa")
    latitude, longitude = maidenhead_center(grid_square)
    return {"callsign": settings.get("callsign", "N0CALL"), "grid_square": grid_square, "latitude": latitude, "longitude": longitude, "display_name": settings.get("display_name", "Dashboard Matrix"), "default_theme": settings.get("default_theme", "matrix-dark")}

@router.put("/settings/station", response_model=StationSettingsResponse)
async def update_station_settings(item: StationSettings, _: None = Depends(require_admin)) -> dict:
    latitude, longitude = maidenhead_center(item.grid_square)
    with connection() as conn:
        conn.execute("INSERT INTO station_settings(key,value) VALUES('callsign',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (item.callsign,))
        conn.execute("INSERT INTO station_settings(key,value) VALUES('grid_square',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (item.grid_square,))
        settings = get_station_settings(conn)
    await manager.broadcast({"event":"configuration_changed"})
    return {"callsign": item.callsign, "grid_square": item.grid_square, "latitude": latitude, "longitude": longitude, "display_name": settings.get("display_name", "Dashboard Matrix"), "default_theme": settings.get("default_theme", "matrix-dark")}

@router.get("/dashboards", response_model=list[Dashboard])
def list_dashboards(include_disabled: bool = False) -> list[dict]:
    with connection() as conn:
        sql = "SELECT * FROM dashboards" + ("" if include_disabled else " WHERE enabled=1") + " ORDER BY sort_order,id"
        items = []
        for row in conn.execute(sql).fetchall():
            item = row_to_dict(row); item["tiles"] = []; items.append(item)
        return items

@router.get("/dashboards/{slug}", response_model=Dashboard)
def read_dashboard(slug: str) -> dict: return _dashboard(slug)

@router.post("/dashboards", response_model=Dashboard, status_code=201)
async def create_dashboard(item: DashboardCreate, _: None = Depends(require_admin)) -> dict:
    with connection() as conn:
        try:
            cur = conn.execute("INSERT INTO dashboards(name,slug,columns,rows,rotate_seconds,is_default,enabled,sort_order) VALUES(?,?,?,?,?,?,?,?)", (item.name,item.slug,item.columns,item.rows,item.rotate_seconds,int(item.is_default),int(item.enabled),item.sort_order))
        except Exception as exc: raise HTTPException(409, f"Dashboard slug already exists: {exc}")
        if item.is_default: conn.execute("UPDATE dashboards SET is_default=0 WHERE id<>?", (cur.lastrowid,))
    await manager.broadcast({"event":"configuration_changed"})
    return _dashboard(item.slug, True)

@router.put("/dashboards/{dashboard_id}", response_model=Dashboard)
async def update_dashboard(dashboard_id: int, item: DashboardUpdate, _: None = Depends(require_admin)) -> dict:
    with connection() as conn:
        if not conn.execute("SELECT 1 FROM dashboards WHERE id=?", (dashboard_id,)).fetchone(): raise HTTPException(404,"Dashboard not found")
        conn.execute("UPDATE dashboards SET name=?,slug=?,columns=?,rows=?,rotate_seconds=?,is_default=?,enabled=?,sort_order=? WHERE id=?", (item.name,item.slug,item.columns,item.rows,item.rotate_seconds,int(item.is_default),int(item.enabled),item.sort_order,dashboard_id))
        if item.is_default: conn.execute("UPDATE dashboards SET is_default=0 WHERE id<>?", (dashboard_id,))
    await manager.broadcast({"event":"configuration_changed"})
    return _dashboard(item.slug, True)

@router.delete("/dashboards/{dashboard_id}", status_code=204)
async def delete_dashboard(dashboard_id: int, _: None = Depends(require_admin)) -> None:
    with connection() as conn:
        if conn.execute("SELECT COUNT(*) FROM dashboards").fetchone()[0] <= 1: raise HTTPException(400,"At least one dashboard is required")
        cur = conn.execute("DELETE FROM dashboards WHERE id=?", (dashboard_id,))
        if cur.rowcount == 0: raise HTTPException(404,"Dashboard not found")
    await manager.broadcast({"event":"configuration_changed"})

@router.get("/tiles", response_model=list[Tile])
def list_tiles(dashboard_id: int | None = None) -> list[dict]:
    with connection() as conn:
        if dashboard_id is None:
            rows = conn.execute("SELECT * FROM tiles ORDER BY dashboard_id,row_pos,col_pos,id").fetchall()
        else:
            rows = conn.execute("SELECT * FROM tiles WHERE dashboard_id=? ORDER BY row_pos,col_pos,id", (dashboard_id,)).fetchall()
        return [row_to_dict(r) for r in rows]

@router.post("/tiles", response_model=Tile, status_code=201)
async def create_tile(tile: TileCreate, _: None = Depends(require_admin)) -> dict:
    with connection() as conn:
        cur=conn.execute("INSERT INTO tiles(dashboard_id,title,tile_type,sources_json,row_pos,col_pos,width,height,locked,refresh_seconds,rotate_seconds,enabled,settings_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(tile.dashboard_id,tile.title,tile.tile_type,json.dumps(tile.sources),tile.row_pos,tile.col_pos,tile.width,tile.height,int(tile.locked),tile.refresh_seconds,tile.rotate_seconds,int(tile.enabled),json.dumps(tile.settings)))
        row=conn.execute("SELECT * FROM tiles WHERE id=?",(cur.lastrowid,)).fetchone()
    await manager.broadcast({"event":"configuration_changed"}); return row_to_dict(row)

@router.put("/tiles/{tile_id}", response_model=Tile)
async def update_tile(tile_id:int,tile:TileUpdate, _: None = Depends(require_admin))->dict:
    with connection() as conn:
        if not conn.execute("SELECT 1 FROM tiles WHERE id=?",(tile_id,)).fetchone(): raise HTTPException(404,"Tile not found")
        conn.execute("UPDATE tiles SET dashboard_id=?,title=?,tile_type=?,sources_json=?,row_pos=?,col_pos=?,width=?,height=?,locked=?,refresh_seconds=?,rotate_seconds=?,enabled=?,settings_json=? WHERE id=?",(tile.dashboard_id,tile.title,tile.tile_type,json.dumps(tile.sources),tile.row_pos,tile.col_pos,tile.width,tile.height,int(tile.locked),tile.refresh_seconds,tile.rotate_seconds,int(tile.enabled),json.dumps(tile.settings),tile_id))
        row=conn.execute("SELECT * FROM tiles WHERE id=?",(tile_id,)).fetchone()
    await manager.broadcast({"event":"configuration_changed"}); return row_to_dict(row)

@router.put("/tiles/positions/batch", status_code=204)
async def update_positions(items:list[TilePosition], _: None = Depends(require_admin))->None:
    with connection() as conn:
        conn.executemany("UPDATE tiles SET row_pos=?,col_pos=?,width=?,height=?,locked=? WHERE id=?",[(i.row_pos,i.col_pos,i.width,i.height,int(i.locked),i.id) for i in items])
    await manager.broadcast({"event":"configuration_changed"})

@router.delete("/tiles/{tile_id}",status_code=204)
async def delete_tile(tile_id:int, _: None = Depends(require_admin))->None:
    with connection() as conn:
        if conn.execute("DELETE FROM tiles WHERE id=?",(tile_id,)).rowcount==0: raise HTTPException(404,"Tile not found")
    await manager.broadcast({"event":"configuration_changed"})

@router.get("/scripts")
def list_scripts() -> list[dict[str, str]]:
    return available_scripts()


@router.get("/scripts/{tile_id}")
async def script_data(tile_id: int) -> dict:
    with connection() as conn:
        row = conn.execute("SELECT settings_json FROM tiles WHERE id=?", (tile_id,)).fetchone()
        station_settings = get_station_settings(conn)
    if not row:
        raise HTTPException(404, "Tile not found")
    settings = json.loads(row[0] or "{}")
    script_name = str(settings.get("script", "")).strip()
    if not script_name:
        raise HTTPException(400, "Script tile is missing settings.script")
    try:
        return await run_script(script_name, settings, station_context(station_settings))
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except TimeoutError as exc:
        raise HTTPException(504, str(exc))
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(502, f"Script error: {exc}")


@router.get("/providers/{tile_id}")
async def provider_data(tile_id:int)->dict:
    with connection() as conn:
        row=conn.execute("SELECT settings_json FROM tiles WHERE id=?",(tile_id,)).fetchone()
    if not row: raise HTTPException(404,"Tile not found")
    settings=json.loads(row[0] or "{}")
    if settings.get("use_station_location"):
        with connection() as conn:
            station = get_station_settings(conn)
        latitude, longitude = maidenhead_center(station.get("grid_square", "EM66hb"))
        settings["latitude"] = latitude
        settings["longitude"] = longitude
    try: return await fetch_provider(settings.get("provider", ""), settings)
    except KeyError as exc: raise HTTPException(400,str(exc))
    except Exception as exc: raise HTTPException(502,f"Provider error: {exc}")



@router.get("/catalog", response_model=list[CatalogItem])
def list_catalog(include_disabled: bool = False) -> list[dict]:
    with connection() as conn:
        sql = "SELECT * FROM catalog_items" + ("" if include_disabled else " WHERE enabled=1") + " ORDER BY sort_order,category,title"
        return [row_to_dict(row) | {"item_id": row["item_id"]} for row in conn.execute(sql).fetchall()]

@router.post("/catalog", response_model=CatalogItem, status_code=201)
async def create_catalog_item(item: CatalogItemCreate, _: None = Depends(require_admin)) -> dict:
    with connection() as conn:
        try:
            conn.execute(
                """INSERT INTO catalog_items(item_id,category,title,description,tile_type,sources_json,refresh_seconds,rotate_seconds,settings_json,enabled,sort_order) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (item.item_id,item.category,item.title,item.description,item.tile_type,json.dumps(item.sources),item.refresh_seconds,item.rotate_seconds,json.dumps(item.settings),int(item.enabled),item.sort_order),
            )
        except Exception as exc:
            raise HTTPException(409, f"Catalog ID already exists: {exc}")
        row = conn.execute("SELECT * FROM catalog_items WHERE item_id=?", (item.item_id,)).fetchone()
    return row_to_dict(row) | {"item_id": row["item_id"]}

@router.put("/catalog/{item_id}", response_model=CatalogItem)
async def update_catalog_item(item_id: str, item: CatalogItemUpdate, _: None = Depends(require_admin)) -> dict:
    with connection() as conn:
        if not conn.execute("SELECT 1 FROM catalog_items WHERE item_id=?", (item_id,)).fetchone():
            raise HTTPException(404, "Catalog item not found")
        if item.item_id != item_id and conn.execute("SELECT 1 FROM catalog_items WHERE item_id=?", (item.item_id,)).fetchone():
            raise HTTPException(409, "New catalog ID already exists")
        conn.execute(
            """UPDATE catalog_items SET item_id=?,category=?,title=?,description=?,tile_type=?,sources_json=?,refresh_seconds=?,rotate_seconds=?,settings_json=?,enabled=?,sort_order=? WHERE item_id=?""",
            (item.item_id,item.category,item.title,item.description,item.tile_type,json.dumps(item.sources),item.refresh_seconds,item.rotate_seconds,json.dumps(item.settings),int(item.enabled),item.sort_order,item_id),
        )
        row = conn.execute("SELECT * FROM catalog_items WHERE item_id=?", (item.item_id,)).fetchone()
    return row_to_dict(row) | {"item_id": row["item_id"]}

@router.delete("/catalog/{item_id}", status_code=204)
async def delete_catalog_item(item_id: str, _: None = Depends(require_admin)) -> None:
    with connection() as conn:
        if conn.execute("DELETE FROM catalog_items WHERE item_id=?", (item_id,)).rowcount == 0:
            raise HTTPException(404, "Catalog item not found")

class CatalogAdd(BaseModel):
    dashboard_id: int
    row_pos: int = Field(default=1, ge=1)
    col_pos: int = Field(default=1, ge=1)
    width: int = Field(default=1, ge=1, le=12)
    height: int = Field(default=1, ge=1, le=12)

@router.post("/catalog/{item_id}/add", response_model=Tile, status_code=201)
async def add_catalog_tile(item_id: str, item: CatalogAdd, _: None = Depends(require_admin)) -> dict:
    with connection() as conn:
        template_row = conn.execute("SELECT * FROM catalog_items WHERE item_id=? AND enabled=1", (item_id,)).fetchone()
        if template_row is None:
            raise HTTPException(404, "Catalog item not found or disabled")
        template = row_to_dict(template_row)
        if not conn.execute("SELECT 1 FROM dashboards WHERE id=?", (item.dashboard_id,)).fetchone():
            raise HTTPException(404, "Dashboard not found")
        cur = conn.execute(
            """INSERT INTO tiles(dashboard_id,title,tile_type,sources_json,row_pos,col_pos,width,height,refresh_seconds,rotate_seconds,enabled,settings_json) VALUES(?,?,?,?,?,?,?,?,?,?,1,?)""",
            (item.dashboard_id, template["title"], template["tile_type"], json.dumps(template["sources"]), item.row_pos, item.col_pos, item.width, item.height, template["refresh_seconds"], template["rotate_seconds"], json.dumps(template["settings"])),
        )
        row = conn.execute("SELECT * FROM tiles WHERE id=?", (cur.lastrowid,)).fetchone()
    await manager.broadcast({"event": "configuration_changed"})
    return row_to_dict(row)



@router.get("/proxy-sources", response_model=list[ProxySource])
def list_proxy_sources(include_disabled: bool = False) -> list[dict]:
    with connection() as conn:
        sql = "SELECT * FROM proxy_sources" + ("" if include_disabled else " WHERE enabled=1") + " ORDER BY name,source_id"
        return [row_to_dict(row) | {"source_id": row["source_id"]} for row in conn.execute(sql).fetchall()]

@router.post("/proxy-sources", response_model=ProxySource, status_code=201)
async def create_proxy_source(item: ProxySourceCreate, _: None = Depends(require_admin)) -> dict:
    with connection() as conn:
        try:
            conn.execute(
                """INSERT INTO proxy_sources(source_id,name,base_url,enabled,strip_x_frame_options,strip_frame_ancestors,inject_base_tag,allow_http,cache_seconds) VALUES(?,?,?,?,?,?,?,?,?)""",
                (item.source_id,item.name,item.base_url,int(item.enabled),int(item.strip_x_frame_options),int(item.strip_frame_ancestors),int(item.inject_base_tag),int(item.allow_http),item.cache_seconds),
            )
        except Exception as exc:
            raise HTTPException(409, f"Proxy source ID already exists: {exc}")
        row = conn.execute("SELECT * FROM proxy_sources WHERE source_id=?", (item.source_id,)).fetchone()
    return row_to_dict(row) | {"source_id": row["source_id"]}

@router.put("/proxy-sources/{source_id}", response_model=ProxySource)
async def update_proxy_source(source_id: str, item: ProxySourceUpdate, _: None = Depends(require_admin)) -> dict:
    with connection() as conn:
        if not conn.execute("SELECT 1 FROM proxy_sources WHERE source_id=?", (source_id,)).fetchone():
            raise HTTPException(404, "Proxy source not found")
        if item.source_id != source_id and conn.execute("SELECT 1 FROM proxy_sources WHERE source_id=?", (item.source_id,)).fetchone():
            raise HTTPException(409, "New proxy source ID already exists")
        conn.execute(
            """UPDATE proxy_sources SET source_id=?,name=?,base_url=?,enabled=?,strip_x_frame_options=?,strip_frame_ancestors=?,inject_base_tag=?,allow_http=?,cache_seconds=? WHERE source_id=?""",
            (item.source_id,item.name,item.base_url,int(item.enabled),int(item.strip_x_frame_options),int(item.strip_frame_ancestors),int(item.inject_base_tag),int(item.allow_http),item.cache_seconds,source_id),
        )
        row = conn.execute("SELECT * FROM proxy_sources WHERE source_id=?", (item.source_id,)).fetchone()
    await manager.broadcast({"event":"configuration_changed"})
    return row_to_dict(row) | {"source_id": row["source_id"]}

@router.delete("/proxy-sources/{source_id}", status_code=204)
async def delete_proxy_source(source_id: str, _: None = Depends(require_admin)) -> None:
    with connection() as conn:
        if conn.execute("DELETE FROM proxy_sources WHERE source_id=?", (source_id,)).rowcount == 0:
            raise HTTPException(404, "Proxy source not found")
    await manager.broadcast({"event":"configuration_changed"})


class PluginStateUpdate(BaseModel):
    enabled: bool = True
    settings: dict = Field(default_factory=dict)
    approvals: list[str] = Field(default_factory=list)
    secret_refs: dict[str, str] = Field(default_factory=dict)

@router.get("/plugins")
def list_plugins() -> list[dict]:
    plugins=discover_plugins()
    with connection() as conn:
        states={r["plugin_id"]:r for r in conn.execute("SELECT * FROM plugin_states").fetchall()}
    result=[]
    for plugin in plugins:
        state=states.get(plugin["id"])
        enabled=bool(state["enabled"]) if state else True
        settings=json.loads(state["settings_json"] or "{}") if state else {}
        approvals=json.loads(state["approvals_json"] or "[]") if state else []
        secret_refs=json.loads(state["secret_refs_json"] or "{}") if state else {}
        result.append(public_plugin(plugin,enabled,settings,approvals,secret_refs))
    return result

@router.put("/plugins/{plugin_id}")
async def update_plugin_state(plugin_id:str,item:PluginStateUpdate,_:None=Depends(require_admin))->dict:
    get_plugin(plugin_id)
    with connection() as conn:
        plugin=get_plugin(plugin_id)
        allowed=set(plugin.get("permissions",[]))
        approvals=sorted(set(item.approvals) & allowed)
        declared_secrets={secret["name"] for secret in plugin.get("secrets",[])}
        secret_refs={
            key:value for key,value in item.secret_refs.items()
            if key in declared_secrets and value and value.replace("_","").isalnum()
        }
        conn.execute(
            "INSERT INTO plugin_states(plugin_id,enabled,settings_json,approvals_json,secret_refs_json) VALUES(?,?,?,?,?) "
            "ON CONFLICT(plugin_id) DO UPDATE SET enabled=excluded.enabled,settings_json=excluded.settings_json,approvals_json=excluded.approvals_json,secret_refs_json=excluded.secret_refs_json",
            (plugin_id,int(item.enabled),json.dumps(item.settings),json.dumps(approvals),json.dumps(secret_refs)),
        )
    await manager.broadcast({"event":"configuration_changed"})
    return {"plugin_id":plugin_id,"enabled":item.enabled,"settings":item.settings,"approvals":approvals,"secret_refs":secret_refs}

class PluginWidgetAdd(BaseModel):
    dashboard_id:int
    widget_id:str
    row_pos:int=Field(default=1,ge=1)
    col_pos:int=Field(default=1,ge=1)

@router.post("/plugins/{plugin_id}/widgets",response_model=Tile,status_code=201)
async def add_plugin_widget(plugin_id:str,item:PluginWidgetAdd,_:None=Depends(require_admin))->dict:
    plugin=get_plugin(plugin_id)
    widget=next((w for w in plugin.get("widgets",[]) if w.get("id")==item.widget_id),None)
    if not widget: raise HTTPException(404,"Plugin widget not found")
    with connection() as conn:
        state=conn.execute("SELECT * FROM plugin_states WHERE plugin_id=?",(plugin_id,)).fetchone()
        if state and not state["enabled"]: raise HTTPException(409,"Plugin is disabled")
        approvals=json.loads(state["approvals_json"] or "[]") if state else []
        secret_refs=json.loads(state["secret_refs_json"] or "{}") if state else {}
        readiness=public_plugin(plugin, True, {}, approvals, secret_refs)
        if not readiness["permission_ready"]:
            raise HTTPException(409,"Approve all declared plugin permissions before adding its cards")
        if not readiness["required_secrets_ready"]:
            raise HTTPException(409,"Configure every required plugin secret environment variable before adding its cards")
        cur=conn.execute("INSERT INTO tiles(dashboard_id,title,tile_type,sources_json,row_pos,col_pos,width,height,refresh_seconds,rotate_seconds,enabled,settings_json) VALUES(?,?,?,?,?,?,?,?,?,?,1,?)",(item.dashboard_id,widget.get("name",item.widget_id),"plugin","[]",item.row_pos,item.col_pos,int(widget.get("default_width",1)),int(widget.get("default_height",1)),int(widget.get("refresh_seconds",300)),0,json.dumps({"plugin":plugin_id,"widget":item.widget_id,"settings":{}})))
        row=conn.execute("SELECT * FROM tiles WHERE id=?",(cur.lastrowid,)).fetchone()
    await manager.broadcast({"event":"configuration_changed"})
    return row_to_dict(row)

@router.get("/plugins/data/{tile_id}")
async def plugin_widget_data(tile_id:int)->dict:
    with connection() as conn:
        row=conn.execute("SELECT settings_json FROM tiles WHERE id=? AND tile_type='plugin'",(tile_id,)).fetchone()
        station=get_station_settings(conn)
        states={r["plugin_id"]:r for r in conn.execute("SELECT * FROM plugin_states").fetchall()}
    if not row: raise HTTPException(404,"Plugin tile not found")
    cfg=json.loads(row[0] or "{}")
    pid=str(cfg.get("plugin",'')); wid=str(cfg.get("widget",''))
    state=states.get(pid)
    if state and not state["enabled"]: raise HTTPException(409,"Plugin disabled")
    plugin_settings=json.loads(state["settings_json"] or "{}") if state else {}
    approvals=json.loads(state["approvals_json"] or "[]") if state else []
    secret_refs=json.loads(state["secret_refs_json"] or "{}") if state else {}
    merged=plugin_settings | dict(cfg.get("settings") or {})
    try:
        return run_plugin_widget(
            pid,wid,merged,station_context(station),
            approvals=approvals,secret_refs=secret_refs,
            timeout_seconds=int(cfg.get("timeout_seconds",20)),
        )
    except FileNotFoundError as exc: raise HTTPException(404,str(exc))
    except (KeyError,PermissionError) as exc: raise HTTPException(400,str(exc))
    except TimeoutError as exc: raise HTTPException(504,str(exc))
    except Exception as exc: raise HTTPException(502,f"Plugin error: {exc}")



class MarketplaceSourceInput(BaseModel):
    name: str = Field(min_length=1,max_length=120)
    index_url: str = Field(min_length=12,max_length=1000)
    enabled: bool = True

@router.get("/marketplace/sources")
def marketplace_sources(_:None=Depends(require_admin))->list[dict]:
    with connection() as conn:
        rows=conn.execute("SELECT * FROM marketplace_sources ORDER BY id").fetchall()
    result=[]
    for r in rows:
        d=dict(r); d["enabled"]=bool(d["enabled"]); d.pop("cached_index_json",None); result.append(d)
    return result

@router.post("/marketplace/sources",status_code=201)
def create_marketplace_source(item:MarketplaceSourceInput,_:None=Depends(require_admin))->dict:
    if not item.index_url.startswith("https://"): raise HTTPException(400,"Marketplace index must use HTTPS")
    with connection() as conn:
        try: cur=conn.execute("INSERT INTO marketplace_sources(name,index_url,enabled) VALUES(?,?,?)",(item.name,item.index_url,int(item.enabled)))
        except Exception as exc: raise HTTPException(409,f"Marketplace source already exists: {exc}")
        row=conn.execute("SELECT * FROM marketplace_sources WHERE id=?",(cur.lastrowid,)).fetchone()
    return {k:(bool(v) if k=='enabled' else v) for k,v in dict(row).items() if k!='cached_index_json'}

@router.put("/marketplace/sources/{source_id}")
def update_marketplace_source(source_id:int,item:MarketplaceSourceInput,_:None=Depends(require_admin))->dict:
    if not item.index_url.startswith("https://"): raise HTTPException(400,"Marketplace index must use HTTPS")
    with connection() as conn:
        if conn.execute("UPDATE marketplace_sources SET name=?,index_url=?,enabled=? WHERE id=?",(item.name,item.index_url,int(item.enabled),source_id)).rowcount==0: raise HTTPException(404,"Marketplace source not found")
    return {"id":source_id,**item.model_dump()}

@router.delete("/marketplace/sources/{source_id}",status_code=204)
def delete_marketplace_source(source_id:int,_:None=Depends(require_admin))->None:
    with connection() as conn:
        if conn.execute("DELETE FROM marketplace_sources WHERE id=?",(source_id,)).rowcount==0: raise HTTPException(404,"Marketplace source not found")

@router.post("/marketplace/sources/{source_id}/sync")
def sync_marketplace_source(source_id:int,_:None=Depends(require_admin))->dict:
    with connection() as conn: row=conn.execute("SELECT * FROM marketplace_sources WHERE id=?",(source_id,)).fetchone()
    if not row: raise HTTPException(404,"Marketplace source not found")
    try: index=fetch_index(row["index_url"])
    except MarketplaceError as exc:
        with connection() as conn: conn.execute("UPDATE marketplace_sources SET last_error=? WHERE id=?",(str(exc),source_id))
        raise HTTPException(502,str(exc))
    now=datetime.now(timezone.utc).isoformat()
    with connection() as conn: conn.execute("UPDATE marketplace_sources SET cached_index_json=?,last_sync=?,last_error=NULL WHERE id=?",(json.dumps(index),now,source_id))
    return {"source_id":source_id,"last_sync":now,"items":len(index["items"])}

@router.get("/marketplace/items")
def marketplace_items(_:None=Depends(require_admin))->list[dict]:
    with connection() as conn:
        sources=conn.execute("SELECT * FROM marketplace_sources WHERE enabled=1 ORDER BY id").fetchall()
        installs={r["item_id"]:dict(r) for r in conn.execute("SELECT * FROM marketplace_installs").fetchall()}
    items=[]
    for source in sources:
        try: index=json.loads(source["cached_index_json"] or '{}')
        except Exception: index={}
        for item in index.get("items",[]):
            installed=installs.get(item["id"])
            items.append(item|{"source_id":source["id"],"source_name":source["name"],"installed_version":installed["version"] if installed else None,"update_available":bool(installed and installed["version"]!=item["version"])})
    return items

@router.post("/marketplace/items/{item_id}/install")
def install_marketplace_item(item_id:str,source_id:int,_:None=Depends(require_admin))->dict:
    with connection() as conn: source=conn.execute("SELECT * FROM marketplace_sources WHERE id=?",(source_id,)).fetchone()
    if not source: raise HTTPException(404,"Marketplace source not found")
    try: index=json.loads(source["cached_index_json"] or '{}')
    except Exception: index={}
    item=next((i for i in index.get("items",[]) if i.get("id")==item_id),None)
    if not item: raise HTTPException(404,"Marketplace item not found; sync the source first")
    if any(p["id"]==item_id and not str(p.get("_path",'')).startswith(str(user_plugins_dir())) for p in discover_plugins()):
        raise HTTPException(409,"A bundled plugin already uses this ID")
    try: manifest=install_plugin(item)
    except MarketplaceError as exc: raise HTTPException(502,str(exc))
    with connection() as conn:
        conn.execute("INSERT INTO marketplace_installs(item_id,source_id,version,sha256,installed_at) VALUES(?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(item_id) DO UPDATE SET source_id=excluded.source_id,version=excluded.version,sha256=excluded.sha256,installed_at=CURRENT_TIMESTAMP",(item_id,source_id,item["version"],item["sha256"]))
        conn.execute("INSERT OR IGNORE INTO plugin_states(plugin_id,enabled,settings_json) VALUES(?,1,'{}')",(item_id,))
    return {"status":"installed","id":item_id,"version":manifest.get("version")}

@router.delete("/marketplace/items/{item_id}")
def uninstall_marketplace_item(item_id:str,_:None=Depends(require_admin))->dict:
    with connection() as conn:
        if not conn.execute("SELECT 1 FROM marketplace_installs WHERE item_id=?",(item_id,)).fetchone(): raise HTTPException(404,"Marketplace installation not found")
        in_use=conn.execute("SELECT COUNT(*) FROM tiles WHERE tile_type='plugin' AND settings_json LIKE ?",(f'%"plugin": "{item_id}"%',)).fetchone()[0]
    if in_use: raise HTTPException(409,"Remove this plugin's tiles before uninstalling it")
    try: uninstall_plugin(item_id)
    except MarketplaceError as exc: raise HTTPException(400,str(exc))
    with connection() as conn:
        conn.execute("DELETE FROM marketplace_installs WHERE item_id=?",(item_id,)); conn.execute("DELETE FROM plugin_states WHERE plugin_id=?",(item_id,))
    return {"status":"uninstalled","id":item_id}

@router.put("/admin/password")
def update_admin_password(item: PasswordChange, _: None = Depends(require_admin)) -> dict[str, str]:
    change_password(item.password)
    return {"status": "ok"}

@router.get("/system/status")
def system_status()->dict:
    disk=shutil.disk_usage(Path.cwd())
    return {"hostname":platform.node() or "unknown","platform":platform.platform(),"python":platform.python_version(),"uptime_seconds":int(time.time()-STARTED_AT),"disk_percent":round(disk.used/disk.total*100,1),"server_time":int(time.time())}
