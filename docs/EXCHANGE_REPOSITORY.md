# Dashboard Matrix Exchange repository

The included `exchange-repo-template/` directory is a ready-to-copy starting
point for `KQ4DLB/dashboard-matrix-exchange`.

## Recommended branch policy

- Protect `main` and require the validation workflow for community pull requests.
- Create an optional `submissions` branch for direct application publishing.
- Give the publishing token repository-contents permission only.
- Never place a token in a layout, screenshot, package, or repository file.

## Direct export path

The application publishes timestamped layout files to:

```text
layouts/<callsign-or-author>/<utc>-<author>-<layout-title>.json
layouts/<callsign-or-author>/<utc>-<author>-<layout-title>.png
```

The Admin page can download the export and, when **Automatically push when
Export is selected** is enabled, publish the same layout and screenshot to the
configured repository in the same action.

## Catalog lifecycle

The repository workflow validates layouts and package manifests, rebuilds
`index.json`, and commits the generated catalog after accepted changes. The
Dashboard Matrix Exchange client reads the raw `index.json` URL.
