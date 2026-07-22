#!/usr/bin/env python3
import json
from ham_common import load_hamqsl, load_noaa_propagation, estimate_hf_bands

ham = load_hamqsl()
if not ham.get("error") and ham.get("bands"):
    payload = {
        "format":"band_conditions",
        "title":"HF Band Conditions",
        "updated":ham.get("updated", "N/A"),
        "stale":ham.get("stale",False),
        "source":"HamQSL",
        "day":[b for b in ham["bands"] if b["time"].lower()=="day"],
        "night":[b for b in ham["bands"] if b["time"].lower()=="night"],
    }
else:
    noaa = load_noaa_propagation()
    if noaa.get("error"):
        payload = {"format":"message","level":"error","title":"HF Band Conditions","message":"Band-condition data is unavailable.","detail":noaa.get("error_detail", "Check NOAA network access.")}
    else:
        bands = estimate_hf_bands(noaa.get("solarflux"), noaa.get("kindex"))
        payload = {
            "format":"band_conditions",
            "title":"Estimated HF Band Conditions",
            "updated":noaa.get("updated", "N/A"),
            "stale":noaa.get("stale",False),
            "source":"NOAA-derived estimate",
            "note":"Estimated from NOAA SFI and Kp. Local noise, season, path, antenna, and ionospheric conditions can differ.",
            "day":bands["day"],
            "night":bands["night"],
        }
print(json.dumps(payload))
