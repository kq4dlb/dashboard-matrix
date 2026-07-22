from __future__ import annotations
import socket

def _cmd(sock: socket.socket, command: str) -> list[str]:
    sock.sendall((command.strip()+"\n").encode())
    data=b""
    while b"\n" not in data and len(data)<8192:
        chunk=sock.recv(4096)
        if not chunk: break
        data+=chunk
    text=data.decode(errors="replace").strip()
    if text.startswith("RPRT "): raise RuntimeError(f"rigctld {command}: {text}")
    return text.splitlines()

def _level(sock,name):
    try:
        rows=_cmd(sock,f"l {name}")
        return float(rows[0]) if rows else None
    except Exception:return None

def _freq(v):
    hz=float(v)
    if hz>=1e9:return f"{hz/1e9:.6f} GHz"
    if hz>=1e6:return f"{hz/1e6:.6f} MHz"
    if hz>=1e3:return f"{hz/1e3:.3f} kHz"
    return f"{hz:.0f} Hz"

def _pct(v): return "N/A" if v is None else f"{max(0,min(1,v))*100:.0f}%"

def render(widget_id, settings, station):
    host=str(settings.get("host","127.0.0.1")); port=int(settings.get("port",4532)); timeout=float(settings.get("timeout",2.0))
    try:
        with socket.create_connection((host,port),timeout=timeout) as s:
            s.settimeout(timeout)
            freq=_cmd(s,"f")[0]
            mode_rows=_cmd(s,"m"); mode=mode_rows[0] if mode_rows else "Unknown"; width=mode_rows[1] if len(mode_rows)>1 else "N/A"
            if widget_id=="radio-compact":
                return {"format":"metrics","title":"Radio","subtitle":f"{host}:{port}","metrics":[{"label":"Frequency","value":_freq(freq),"status":"good"},{"label":"Mode","value":mode},{"label":"Callsign","value":station.get("CALLSIGN","")} ]}
            rf=_level(s,"RFPOWER"); af=_level(s,"AF"); sql=_level(s,"SQL"); swr=_level(s,"SWR"); strength=_level(s,"STRENGTH")
        metrics=[{"label":"Frequency","value":_freq(freq),"status":"good"},{"label":"Mode","value":mode},{"label":"Passband","value":f"{width} Hz"},{"label":"RF Power","value":_pct(rf)},{"label":"Volume","value":_pct(af)},{"label":"Squelch","value":_pct(sql)}]
        if swr is not None: metrics.append({"label":"SWR","value":f"{swr:.2f}"})
        if strength is not None: metrics.append({"label":"Signal","value":f"{strength:.0f}"})
        return {"format":"metrics","title":"Hamlib Radio Status","subtitle":f"{host}:{port}","metrics":metrics}
    except Exception as exc:
        return {"format":"message","title":"Radio Offline","status":"error","message":f"Unable to reach rigctld at {host}:{port}: {exc}"}
