# Dashboard Matrix Plugin SDK

Create `user_plugins/my-plugin/manifest.json`:

```json
{
  "id": "my-plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "author": "Your Name",
  "description": "Example Dashboard Matrix plugin",
  "widgets": [
    {
      "id": "status",
      "name": "My Status",
      "module": "plugin.py",
      "default_width": 2,
      "default_height": 1,
      "refresh_seconds": 30
    }
  ]
}
```

Create `plugin.py`:

```python
def render(widget_id, settings, station):
    return {
        "format": "metrics",
        "title": "My Status",
        "metrics": [
            {"label": "Callsign", "value": station["CALLSIGN"]},
            {"label": "State", "value": "Online"}
        ]
    }
```

Restart Dashboard Matrix. The plugin appears under **Plugin SDK & installed plugins** in Admin. Shared plugin settings are stored in SQLite and merged with per-tile settings. Supported output formats currently include `metrics`, `band_conditions`, `solar_weather`, `message`, `text`, and generic JSON.

## Manifest fields

- `id`: lowercase letters, numbers, and hyphens
- `name`, `version`, `author`, `description`
- `widgets`: one or more widget definitions
- widget fields: `id`, `name`, `description`, `module`, `default_width`, `default_height`, `refresh_seconds`

## Runtime contract

`render(widget_id, settings, station)` must return a dictionary. `station` contains callsign, grid square, latitude, and longitude aliases. Plugins run inside the Dashboard Matrix Python process, so install only trusted plugins.
