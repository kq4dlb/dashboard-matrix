# Dashboard Matrix GitHub Widget Marketplace

Dashboard Matrix reads a versioned `index.json` from an HTTPS URL, normally GitHub raw content. Packages are ZIP archives containing one plugin directory with `manifest.json` and Python modules.

## Security model

* Administrators explicitly add, enable, and sync sources.
* Every package must include a SHA-256 checksum in the index.
* ZIP path traversal and oversized files are rejected.
* Marketplace plugins install only under `user_plugins/`.
* Bundled plugin IDs cannot be overwritten.
* Plugins execute with Dashboard Matrix permissions; install only trusted code.

A repository-ready starter marketplace is supplied separately as `dashboard-matrix-exchange-starter.zip`.
