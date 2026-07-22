from __future__ import annotations
import json,queue,time,os
def render(widget_id,settings,station):
 try: import paho.mqtt.client as mqtt
 except ImportError:return {"format":"message","title":"MQTT Dependency Missing","status":"warning","message":"Install optional dependency: pip install paho-mqtt"}
 host=str(settings.get("host","127.0.0.1")); port=int(settings.get("port",1883)); topic=str(settings.get("topic","station/status")); timeout=float(settings.get("timeout",3)); q=queue.Queue(maxsize=1)
 def on_message(client,userdata,msg):
  try:q.put_nowait((msg.payload.decode(errors="replace"),msg.retain,msg.qos))
  except queue.Full:pass
 c=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
 if settings.get("username"):c.username_pw_set(str(settings["username"]),str(os.environ.get("DASHBOARD_MATRIX_SECRET_PASSWORD") or settings.get("password","")))
 c.on_message=on_message
 try:
  c.connect(host,port,keepalive=max(10,int(timeout*3))); c.subscribe(topic); c.loop_start(); payload,retain,qos=q.get(timeout=timeout)
  try:
   parsed=json.loads(payload)
   if isinstance(parsed,dict): metrics=[{"label":str(k),"value":str(v)} for k,v in list(parsed.items())[:12]]
   else: metrics=[{"label":"Value","value":str(parsed)}]
  except Exception: metrics=[{"label":"Value","value":payload}]
  metrics.extend([{"label":"Topic","value":topic},{"label":"QoS / Retained","value":f"{qos} / {'Yes' if retain else 'No'}"}])
  return {"format":"metrics","title":"MQTT","subtitle":f"{host}:{port}","metrics":metrics}
 except Exception as exc:return {"format":"message","title":"MQTT Offline","status":"error","message":f"{host}:{port} · {topic}: {exc}"}
 finally:
  try:c.loop_stop(); c.disconnect()
  except Exception:pass
