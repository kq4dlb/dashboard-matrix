from __future__ import annotations
import hashlib, io, json, re, shutil, tempfile, urllib.request, zipfile
from pathlib import Path
from app.paths import data_dir, user_plugins_dir
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
USER_PLUGIN_DIR = user_plugins_dir()
BACKUP_DIR = data_dir() / "plugin_backups"
ITEM_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MAX_INDEX_BYTES = 2_000_000
MAX_PACKAGE_BYTES = 25_000_000

class MarketplaceError(RuntimeError): pass

def _download(url: str, limit: int) -> bytes:
    parsed=urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise MarketplaceError("Marketplace URLs must use HTTPS")
    req=urllib.request.Request(url, headers={"User-Agent":"Dashboard-Matrix-Exchange/0.1","Accept":"application/json, application/zip, application/octet-stream"})
    with urllib.request.urlopen(req, timeout=20) as response:
        data=response.read(limit+1)
    if len(data)>limit: raise MarketplaceError("Remote marketplace file is too large")
    return data

def fetch_index(url: str) -> dict[str, Any]:
    try: data=json.loads(_download(url, MAX_INDEX_BYTES).decode("utf-8"))
    except Exception as exc: raise MarketplaceError(f"Unable to read marketplace index: {exc}") from exc
    if data.get("schema_version") != 1 or not isinstance(data.get("items"), list):
        raise MarketplaceError("Unsupported marketplace index format")
    clean=[]
    for item in data["items"]:
        if not isinstance(item,dict): continue
        iid=str(item.get("id",'')); kind=str(item.get("kind","plugin"))
        if not ITEM_ID.fullmatch(iid) or kind not in {"plugin"}: continue
        if not all(item.get(k) for k in ("name","version","download_url","sha256")): continue
        clean.append({
            "id":iid,"kind":kind,"name":str(item["name"]),"version":str(item["version"]),
            "description":str(item.get("description",'')),"author":str(item.get("author","Unknown")),
            "category":str(item.get("category","Other")),"download_url":str(item["download_url"]),
            "sha256":str(item["sha256"]).lower(),"homepage":str(item.get("homepage",'')),
            "min_dashboard_matrix_version":str(item.get("min_dashboard_matrix_version", "0.1.0-beta")),"tags":list(item.get("tags",[])),
            "screenshots":list(item.get("screenshots",[])),
        })
    return {"name":str(data.get("name","Marketplace")),"description":str(data.get("description",'')),"items":clean}

def _safe_extract(zf: zipfile.ZipFile, destination: Path) -> None:
    dest=destination.resolve()
    for info in zf.infolist():
        target=(destination/info.filename).resolve()
        if not target.is_relative_to(dest): raise MarketplaceError("Package contains an unsafe path")
        if info.file_size > 10_000_000: raise MarketplaceError("Package contains an oversized file")
    zf.extractall(destination)

def install_plugin(item: dict[str,Any]) -> dict[str,Any]:
    plugin_id=item["id"]
    if not ITEM_ID.fullmatch(plugin_id): raise MarketplaceError("Invalid plugin ID")
    package=_download(item["download_url"], MAX_PACKAGE_BYTES)
    digest=hashlib.sha256(package).hexdigest()
    if digest != item["sha256"].lower(): raise MarketplaceError("Package checksum did not match marketplace index")
    with tempfile.TemporaryDirectory(prefix="dashboard-matrix-exchange-") as temp:
        stage=Path(temp)
        try:
            with zipfile.ZipFile(io.BytesIO(package)) as zf: _safe_extract(zf, stage)
        except zipfile.BadZipFile as exc: raise MarketplaceError("Package is not a valid ZIP file") from exc
        candidates=list(stage.rglob("manifest.json"))
        if len(candidates)!=1: raise MarketplaceError("Package must contain exactly one plugin manifest")
        source=candidates[0].parent
        try: manifest=json.loads((source/"manifest.json").read_text(encoding="utf-8"))
        except Exception as exc: raise MarketplaceError(f"Invalid plugin manifest: {exc}") from exc
        if manifest.get("id") != plugin_id or str(manifest.get("version")) != str(item["version"]):
            raise MarketplaceError("Package manifest ID/version does not match marketplace index")
        USER_PLUGIN_DIR.mkdir(parents=True,exist_ok=True); BACKUP_DIR.mkdir(parents=True,exist_ok=True)
        target=USER_PLUGIN_DIR/plugin_id
        if target.exists():
            backup=BACKUP_DIR/f"{plugin_id}-backup"
            if backup.exists(): shutil.rmtree(backup)
            shutil.copytree(target,backup); shutil.rmtree(target)
        shutil.copytree(source,target)
    return manifest

def uninstall_plugin(plugin_id:str)->None:
    if not ITEM_ID.fullmatch(plugin_id): raise MarketplaceError("Invalid plugin ID")
    target=USER_PLUGIN_DIR/plugin_id
    if not target.exists(): raise MarketplaceError("Installed marketplace plugin was not found")
    shutil.rmtree(target)
