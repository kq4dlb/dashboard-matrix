# Administration interface

Dashboard Matrix Administration is divided into five tabbed workspaces:

- **Overview** — station identity, administrator password, product updates,
  themes, and version information.
- **Dashboards & Cards** — dashboard definitions, card configuration, and the
  configured-card inventory.
- **Layouts & Sharing** — layout import, conflict handling, screenshots,
  downloads, and GitHub Exchange publishing.
- **Sources & Catalog** — controlled iframe proxy sources, diagnostics, and
  reusable catalog items.
- **Extensions** — Dashboard Matrix Exchange sources, community packages,
  plugins, permissions, and secret mappings.

## Direct links

Each workspace has a stable URL hash:

```text
/admin#admin-overview
/admin#admin-dashboards
/admin#admin-layouts
/admin#admin-sources
/admin#admin-extensions
```

The last selected workspace is remembered in browser storage. A valid URL hash
has priority over the remembered selection.

## Keyboard navigation

When focus is on a tab:

- `Left Arrow` or `Up Arrow` selects the previous tab.
- `Right Arrow` or `Down Arrow` selects the next tab.
- `Home` selects the first tab.
- `End` selects the last tab.

The interface uses `tablist`, `tab`, and `tabpanel` roles with linked
`aria-controls` and `aria-labelledby` attributes.

## Compatibility

The tabbed interface changes only presentation and navigation. Existing form
IDs, API endpoints, JavaScript workflows, and database behavior are preserved.
