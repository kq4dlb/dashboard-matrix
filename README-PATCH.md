# Apply the theme/title-bar repair

Copy this directory over the repository root, then run:

```bash
pytest -q
python matrix.py
```

Perform one hard browser refresh after restarting the application. Static asset
URLs now include the application version, so future releases should invalidate
old CSS and JavaScript automatically.
