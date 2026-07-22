#!/usr/bin/env python3
import json
import os

print(json.dumps({
    "format": "metrics",
    "title": "Station Summary",
    "updated": "Live station configuration",
    "stale": False,
    "metrics": [
        {"label": "Callsign", "value": os.environ.get("DASHBOARD_MATRIX_CALLSIGN", "N/A")},
        {"label": "Grid", "value": os.environ.get("DASHBOARD_MATRIX_GRIDSQUARE", "N/A")},
        {"label": "Latitude", "value": os.environ.get("DASHBOARD_MATRIX_LAT", "N/A")},
        {"label": "Longitude", "value": os.environ.get("DASHBOARD_MATRIX_LONG", "N/A")},
    ],
}))
