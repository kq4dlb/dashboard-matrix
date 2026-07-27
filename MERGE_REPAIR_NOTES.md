# Current-main merge repair

This repair restores the tested Administration tabs, Matrix Light default behavior,
and saved station identity display after a merge regression.

## Repaired behavior

- Administration tab JavaScript and CSS are included and tested as served assets.
- The dashboard theme fallback reads the server-provided default and falls back to Matrix Light.
- Callsign, grid square, latitude, and longitude are shown as separate title-bar values.
- Administration shows a live saved-station summary after loading and saving.
- Configuration WebSocket updates reload station identity and the current theme package.
