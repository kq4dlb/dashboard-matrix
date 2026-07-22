# Contributing to Dashboard Matrix Exchange

Dashboard Matrix Exchange accepts community layouts, plugins, themes, and map
providers.

## Submission paths

```text
layouts/<author-or-callsign>/<timestamp>-<author>-<title>.json
layouts/<author-or-callsign>/<timestamp>-<author>-<title>.png
plugins/<package-id>/manifest.json
themes/<package-id>/manifest.json
map-providers/<package-id>/manifest.json
```

## Layout submissions

1. Export from Dashboard Matrix Administration.
2. Remove or replace private hosts, coordinates, tokens, usernames, and local
   network addresses that should not be public.
3. Include a screenshot when it does not reveal private information.
4. Submit through a pull request, or publish to the repository's designated
   `submissions` branch when direct application publishing is enabled.

## Package submissions

- Package IDs must be lowercase and hyphenated.
- Include author, version, description, license, minimum Dashboard Matrix
  version, download URL, and SHA-256 digest.
- Declare all plugin permissions and secrets.
- Do not include credentials or secret values.
- Keep third-party code licensing compatible with the package license.

## Validation

The repository workflow validates JSON schemas and rebuilds `index.json`.
Changes should not edit generated index entries manually.
