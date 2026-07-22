# Plugin permissions and secrets

Dashboard Matrix plugins execute in a separate Python process with a filtered
environment and a hard timeout. A manifest declares permissions such as:

```json
{
  "permissions": ["network", "secrets"],
  "secrets": [
    {
      "name": "api_key",
      "description": "Provider API key",
      "required": true
    }
  ]
}
```

Administrators must explicitly approve every declared permission before a
widget runs. The beta worker also blocks common network, subprocess, and file
operations when the corresponding permission is not approved. This is a
risk-reduction boundary, not a complete operating-system sandbox; install only
plugins you trust and verify marketplace checksums.

Secret values are never stored in SQLite or exported in a layout. The plugin
state stores only an environment-variable reference:

```json
{
  "api_key": "MY_PROVIDER_API_KEY"
}
```

The worker receives the value as `DASHBOARD_MATRIX_SECRET_API_KEY`. The Admin
UI displays whether a referenced variable is configured but never returns its
value.
