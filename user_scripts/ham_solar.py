#!/usr/bin/env python3
import json
from ham_common import load_noaa, val

noaa = load_noaa()
alerts=[]
for item in noaa.get("alerts",[]):
    if isinstance(item,dict):
        alerts.append(str(item.get("message") or item.get("summary") or item.get("product_id") or "Alert").replace("\n"," ")[:160])
print(json.dumps({
    "format":"solar_weather",
    "title":"NOAA Space Weather",
    "stale":noaa.get("stale",False),
    "kp":{"value":val(noaa.get("kp"),"kp","estimated_kp"),"time":val(noaa.get("kp"),"time_tag","time")},
    "forecast":{"value":val(noaa.get("kp_forecast"),"kp","predicted_kp"),"time":val(noaa.get("kp_forecast"),"time_tag","time")},
    "solar_wind":{"speed":val(noaa.get("plasma"),"speed","bulk_speed"),"density":val(noaa.get("plasma"),"density","proton_density"),"temperature":val(noaa.get("plasma"),"temperature"),"time":val(noaa.get("plasma"),"time_tag","time")},
    "magnetic":{"bt":val(noaa.get("mag"),"bt"),"bz":val(noaa.get("mag"),"bz_gsm","bz"),"time":val(noaa.get("mag"),"time_tag","time")},
    "alerts":alerts[-3:]
}))
