# Theme package SDK

A theme package is a directory under `themes/` or `user_themes/`:

```text
themes/example-theme/
  manifest.json
  theme.css
```

The manifest format is:

```json
{
  "id": "example-theme",
  "name": "Example Theme",
  "version": "1.0.0",
  "author": "Your Name",
  "description": "A short description.",
  "color_scheme": "light",
  "stylesheet": "theme.css"
}
```

Theme CSS should override Dashboard Matrix variables instead of copying the
complete application stylesheet:

```css
:root {
  color-scheme: light;
  --matrix-bg: #f2f5f7;
  --matrix-header: #ffffff;
  --matrix-sidebar: #f8fafc;
  --panel: #ffffff;
  --panel-header: #edf2f5;
  --border: #b7c3cc;
  --text: #17222b;
  --muted: #526674;
  --accent: #006fa6;
  --button-bg: #e5edf2;
  --input-bg: #ffffff;
  --shadow: #4055662b;
}
```

The bundled `matrix-light` theme is the reference implementation.
