# Dashboard Matrix current-main merge repair

Copy these files over the repository root, then run:

```bash
pytest -q
python matrix.py
```

The patch restores and verifies:

- tabbed Administration assets
- Matrix Light server default behavior
- saved callsign, grid square, latitude, and longitude display
- Admin saved-station summary
- dashboard title-bar station values
