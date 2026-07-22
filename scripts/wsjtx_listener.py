#!/usr/bin/env python3
"""Minimal WSJT-X UDP Status packet listener for Dashboard Matrix."""
from __future__ import annotations
import argparse,json,socket,struct,time
from pathlib import Path
MAGIC=0xADBCCBDA
class Reader:
 def __init__(self,b): self.b=b; self.i=0
 def take(self,n):
  if self.i+n>len(self.b): raise ValueError("truncated packet")
  v=self.b[self.i:self.i+n]; self.i+=n; return v
 def u8(self): return struct.unpack(">B",self.take(1))[0]
 def u32(self): return struct.unpack(">I",self.take(4))[0]
 def u64(self): return struct.unpack(">Q",self.take(8))[0]
 def boolean(self): return bool(self.u8())
 def qstr(self):
  n=self.u32()
  if n==0xffffffff:return ""
  return self.take(n).decode("utf-8",errors="replace")
def parse(data):
 r=Reader(data)
 if r.u32()!=MAGIC: raise ValueError("not WSJT-X")
 schema=r.u32(); ptype=r.u32(); uid=r.qstr()
 if ptype!=1:return None
 out={"schema":schema,"id":uid,"dial_frequency":r.u64(),"mode":r.qstr(),"dx_call":r.qstr(),"report":r.qstr(),"tx_mode":r.qstr(),"tx_enabled":r.boolean(),"transmitting":r.boolean(),"decoding":r.boolean(),"rx_df":r.u32(),"tx_df":r.u32(),"de_call":r.qstr(),"de_grid":r.qstr(),"dx_grid":r.qstr(),"tx_watchdog":r.boolean(),"sub_mode":r.qstr(),"fast_mode":r.boolean()}
 try:
  out.update({"special_operation_mode":r.u8(),"frequency_tolerance":r.u32(),"tr_period":r.u32(),"configuration_name":r.qstr(),"tx_message":r.qstr()})
 except ValueError: pass
 out["received_at"]=time.time(); return out
def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--host",default="0.0.0.0"); ap.add_argument("--port",type=int,default=2237); ap.add_argument("--output",default="data/wsjtx_status.json"); a=ap.parse_args()
 out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
 s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind((a.host,a.port))
 print(f"Dashboard Matrix WSJT-X listener on {a.host}:{a.port} -> {out}",flush=True)
 while True:
  data,_=s.recvfrom(65535)
  try:
   parsed=parse(data)
   if parsed:
    tmp=out.with_suffix(out.suffix+".tmp"); tmp.write_text(json.dumps(parsed),encoding="utf-8"); tmp.replace(out)
  except Exception as exc: print(f"WSJT-X packet error: {exc}",flush=True)
if __name__=="__main__": main()
