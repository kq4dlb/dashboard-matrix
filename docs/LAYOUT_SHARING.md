# Layout import, export, and sharing

Dashboard Matrix can import, export, preview, and publish complete dashboard
layouts from **Administration → Layouts**.

## Exported content

A layout package can include:

- Dashboard names, slugs, grid dimensions, ordering, and rotation
- Card position, dimensions, type, sources, and refresh intervals
- Card settings, including plugin and script references
- Required plugin and script names
- Optional portable station settings such as callsign, grid square, and map profile
- Optional browser-captured dashboard screenshot
- Title, description, tags, author, and license metadata

A layout export never includes:

- Administrator password hashes
- GitHub access tokens
- Plugin secret values
- Plugin runtime state
- Update-check state or local audit records

## Administration workflow

1. Open **Administration → Layouts**.
2. Enter export title, description, and tags.
3. Select whether portable station settings should be included.
4. Capture or refresh the screenshot preview when desired.
5. Choose **Download JSON** for a local-only export.
6. Enable **Publish automatically after export** to download and publish the
   same export package in one action.

The GitHub token is accepted for the current request only or read from
`DASHBOARD_MATRIX_LAYOUT_GITHUB_TOKEN`. Dashboard Matrix stores the repository,
branch, folder, and auto-publish preference, but never stores the token.

## Layout import and conflict handling

Select a JSON layout file and choose **Analyze** before importing. The analysis
shows incoming dashboards, cards, dependencies, schema issues, and naming
conflicts.

Available conflict strategies:

- `rename`: preserve existing dashboards and assign unique incoming slugs
- `replace`: replace dashboards with matching slugs
- `skip`: ignore dashboards whose slugs already exist
- `merge`: add incoming cards beneath the existing card rows

Imports are transactional. A validation failure does not leave a partially
imported layout.

## Command-line export

```bash
python scripts/export-layout.py \
  --title "KQ4DLB Home Dashboard" \
  --description "Home station dashboard set" \
  --tag home \
  --tag hf \
  --include-station
```

Publish directly:

```bash
export DASHBOARD_MATRIX_LAYOUT_GITHUB_TOKEN="github_pat_..."
python scripts/export-layout.py \
  --publish \
  --repository KQ4DLB/dashboard-matrix-exchange \
  --branch submissions \
  --folder layouts \
  --title "KQ4DLB Home Dashboard" \
  --screenshot dashboard.png
```

A fine-grained GitHub token should be limited to the Exchange repository and
have only **Contents: Read and write** permission.

## API

```text
GET  /api/layout-exports/current
GET  /api/layout-exports/download
POST /api/layout-exports/publish
POST /api/layout-imports/analyze
POST /api/layout-imports
```

All endpoints require an authenticated Administrator session.

Published paths use the author/callsign and a high-resolution UTC timestamp:

```text
layouts/kq4dlb/20260715T231500123456Z-kq4dlb-home-dashboard.json
layouts/kq4dlb/20260715T231500123456Z-kq4dlb-home-dashboard.png
```
