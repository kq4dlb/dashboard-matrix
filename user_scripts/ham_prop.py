#!/usr/bin/env python3
import json
from ham_common import load_propagation_with_fallback

ham = load_propagation_with_fallback()
if ham.get("error"):
    print(json.dumps({"format":"message","level":"error","title":"Propagation Metrics","message":"Propagation data is unavailable.","detail":ham.get("error_detail", "Check NOAA network access.")}))
else:
    source = ham.get("source", "Unknown")
    metrics = [
        {"label":"SFI","value":ham.get("solarflux", "N/A")},
        {"label":"Sunspots","value":ham.get("sunspots", "N/A")},
        {"label":"A index","value":ham.get("aindex", "N/A")},
        {"label":"K index","value":ham.get("kindex", "N/A")},
        {"label":"X-Ray","value":ham.get("xray", "N/A")},
        {"label":"MUF","value":ham.get("muf", "N/A")},
        {"label":"foF2","value":ham.get("fof2", "N/A")},
        {"label":"Geomagnetic","value":ham.get("geomagfield", "N/A")},
        {"label":"Source","value":source},
    ]
    print(json.dumps({
        "format":"metrics",
        "title":"Propagation Metrics" + (" (NOAA)" if ham.get("estimated") else ""),
        "updated":ham.get("updated", "N/A"),
        "stale":ham.get("stale",False),
        "note":"HamQSL was unavailable; official NOAA SWPC values are being used. MUF and foF2 require an ionosonde source." if ham.get("estimated") else "",
        "metrics":metrics,
    }))
