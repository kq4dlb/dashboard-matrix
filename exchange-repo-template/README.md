# Dashboard Matrix Exchange

This repository is the community package and layout index for Dashboard Matrix.

## Repository structure

```text
index.json                  Generated searchable catalog
layouts/<author>/           Layout JSON and matching screenshots
themes/<package-id>/        Theme packages
plugins/<package-id>/       Plugin release metadata or archives
map-providers/<package-id>/ Map-provider packages
schemas/                    JSON Schemas used by validation
scripts/rebuild_index.py    Deterministic catalog builder
.github/workflows/          Pull-request validation and index rebuild
```

## Layout contribution

Dashboard Matrix can publish a layout directly through the GitHub Contents API.
It creates timestamped files under `layouts/<callsign-or-author>/`. A screenshot
is optional. The publisher never writes a GitHub token into the layout or the
Dashboard Matrix database.

Direct publishing to a protected `main` branch requires a token or GitHub App
with appropriate repository contents permission. Community repositories may
instead use a dedicated submissions branch and a pull-request workflow.

## Package contribution

Every package directory contains a `manifest.json`. Downloadable archives must
include a SHA-256 checksum. The validation workflow rejects duplicate IDs and invalid layout or package metadata. Dashboard Matrix verifies package SHA-256 checksums again at installation time.

## Catalog

`index.json` is generated. Do not edit it by hand. Run:

```bash
python scripts/rebuild_index.py
```
