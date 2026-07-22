from __future__ import annotations
import json,time,urllib.parse,urllib.request,os
def render(widget_id,settings,station):
 key=str(os.environ.get("DASHBOARD_MATRIX_SECRET_API_KEY") or settings.get("api_key","")).strip(); call=str(settings.get("callsign") or station.get("CALLSIGN","")).upper(); timeout=float(settings.get("timeout",8))
 if not key:return {"format":"message","title":"APRS Setup Required","status":"warning","message":"Add your APRS.fi API key in the plugin settings."}
 url="https://api.aprs.fi/api/get?"+urllib.parse.urlencode({"name":call,"what":"loc","apikey":key,"format":"json"})
 try:
  req=urllib.request.Request(url,headers={"User-Agent":"Dashboard-Matrix-APRS/1.0"})
  with urllib.request.urlopen(req,timeout=timeout) as r:data=json.load(r)
  if data.get("result")!="ok" or not data.get("entries"):raise RuntimeError(data.get("description") or "station not found")
  e=data["entries"][0]; last=int(e.get("lasttime",0)); age=max(0,int(time.time()-last)) if last else 0
  metrics=[{"label":"Callsign","value":e.get("name",call),"status":"good"},{"label":"Position","value":f"{e.get('lat','?')}, {e.get('lng','?')}"},{"label":"Last Heard","value":f"{age//60} min ago"},{"label":"Comment","value":e.get("comment") or "—"}]
  for label,key2,suffix in (("Speed","speed"," km/h"),("Course","course","°"),("Altitude","altitude"," m"),("Path","path","")):
   if e.get(key2) not in (None,""):metrics.append({"label":label,"value":f"{e[key2]}{suffix}"})
  return {"format":"metrics","title":"APRS Station","subtitle":call,"metrics":metrics}
 except Exception as exc:return {"format":"message","title":"APRS Unavailable","status":"error","message":str(exc)}
