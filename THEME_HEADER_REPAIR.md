# Theme and title-bar merge repair

This repair restores the theme component contract and dashboard header layout
that were partially lost during a merge.

## Root causes

- Component styling was spread across the legacy dashboard stylesheet, theme
  packages, and Admin tab stylesheet. Later rules could reintroduce dark card
  surfaces even when Matrix Light was selected.
- The dashboard template contained `station-meta`, version, and update elements,
  but current-main CSS did not contain the matching layout rules.
- Static assets had no version query, so browsers could continue using CSS and
  JavaScript from before the merge after a service restart.

## Repair

- Adds `app/static/css/theme-components.css`, loaded after the selected theme and
  page-specific CSS.
- Makes dashboard cards, catalog cards, configured-item rows, forms, code boxes,
  plugin permission boxes, and Admin panels consume semantic theme variables.
- Rebuilds the title bar with explicit grid areas for dashboard name, callsign,
  grid, latitude, longitude, connection state, clock, version, update icon, and
  controls.
- Adds responsive title-bar behavior without dropping station data at normal
  tablet widths.
- Adds version query strings to core CSS and JavaScript assets to prevent stale
  browser cache after upgrades.
