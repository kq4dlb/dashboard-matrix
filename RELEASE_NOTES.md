# Dashboard Matrix 0.1.0-beta

This is the first public beta of KQ4DLB Dashboard Matrix as an independent,
self-hosted dashboard application.

The release is intended for hands-on testing. Begin with a clean data directory,
complete the first-run wizard, choose a starter template, and test dashboard
editing, proxy diagnostics, plugins, themes, layout import/export, screenshot
capture, and Exchange publishing. The Administration page is organized into five
tabbed workspaces with keyboard navigation and remembered selection.

This theme refinement makes Matrix Light the default for new installations, adds
a persistent **Make default** action in Administration, and removes remaining
hard-coded dark surfaces from catalog, provider, diagnostics, form, and card
components. Existing installations can choose Matrix Light under
**Administration → Overview → Theme packages**.


This update adds the installed version to the dashboard header and displays a
single upward-arrow icon when the selected GitHub release channel has a newer
version. It also adds merge-driven version synchronization, annotated tags,
automatic GitHub releases, source packages, Python packages, Windows executables,
Raspberry Pi bundles, checksums, and categorized generated release notes.

## Important beta notes

- Screenshot capture requires Playwright and a Chromium browser installation.
- Direct GitHub publishing requires a repository token with appropriate contents
  permission or the server environment token.
- Plugin permission controls reduce accidental access but are not an operating-
  system security sandbox.
- The Raspberry Pi full-image job is optional and requires a compatible
  self-hosted ARM64 runner; the normal Raspberry Pi installer is included.
