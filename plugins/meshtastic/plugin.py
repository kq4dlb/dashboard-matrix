from __future__ import annotations
def render(widget_id,settings,station):
 try: from meshtastic.serial_interface import SerialInterface
 except ImportError:return {"format":"message","title":"Meshtastic Dependency Missing","status":"warning","message":"Install optional dependencies: pip install meshtastic pyserial"}
 iface=None
 try:
  port=settings.get("port") or None; iface=SerialInterface(devPath=port)
  node=iface.getMyNodeInfo() or {}; user=node.get("user",{}); metrics=node.get("deviceMetrics",{}); pos=node.get("position",{})
  rows=[{"label":"Node","value":user.get("longName") or user.get("shortName") or str(node.get("num","Unknown")),"status":"good"},{"label":"Node ID","value":user.get("id") or "—"}]
  for label,key,suffix in (("Battery","batteryLevel","%"),("Voltage","voltage"," V"),("Channel Utilization","channelUtilization","%"),("Air Util TX","airUtilTx","%")):
   if metrics.get(key) is not None: rows.append({"label":label,"value":f"{metrics[key]}{suffix}"})
  if pos.get("latitude") is not None: rows.append({"label":"Position","value":f"{pos.get('latitude')}, {pos.get('longitude')}"})
  rows.append({"label":"Known Nodes","value":str(len(getattr(iface,"nodes",{}) or {}))})
  return {"format":"metrics","title":"Meshtastic","subtitle":port or "Auto-detected serial","metrics":rows}
 except Exception as exc:return {"format":"message","title":"Meshtastic Offline","status":"error","message":str(exc)}
 finally:
  try:
   if iface:iface.close()
  except Exception:pass
