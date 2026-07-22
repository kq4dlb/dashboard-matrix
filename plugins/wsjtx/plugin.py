from __future__ import annotations
import json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def _freq(hz):
    try:return f"{float(hz)/1e6:.6f} MHz"
    except:return "N/A"
def render(widget_id,settings,station):
    path=Path(str(settings.get("status_file","data/wsjtx_status.json")))
    if not path.is_absolute(): path=ROOT/path
    try:data=json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:return {"format":"message","title":"WSJT-X Offline","status":"error","message":f"No listener status at {path}: {exc}"}
    age=max(0,time.time()-float(data.get("received_at",0))); stale=int(settings.get("stale_seconds",30))
    state="Transmitting" if data.get("transmitting") else "Decoding" if data.get("decoding") else "Receiving"
    status="warning" if age>stale else "good"
    return {"format":"metrics","title":"WSJT-X","subtitle":f"{state} · {age:.0f}s ago","metrics":[
      {"label":"Frequency","value":_freq(data.get("dial_frequency")),"status":status},{"label":"Mode","value":data.get("mode") or "N/A"},
      {"label":"TX Mode","value":data.get("tx_mode") or "N/A"},{"label":"DX Call","value":data.get("dx_call") or "—"},
      {"label":"DX Grid","value":data.get("dx_grid") or "—"},{"label":"RX / TX DF","value":f"{data.get('rx_df','—')} / {data.get('tx_df','—')} Hz"},
      {"label":"TX Enabled","value":"Yes" if data.get("tx_enabled") else "No"},{"label":"Message","value":data.get("tx_message") or "—"}
    ]}
