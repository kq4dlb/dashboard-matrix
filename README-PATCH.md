# Dashboard Matrix Administration tabs patch

Apply these files over the current `main` branch of
`https://github.com/kq4dlb/dashboard-matrix`.

The patch adds a five-tab Administration workspace while preserving existing
form IDs, API endpoints, and backend behavior.

Run after applying:

```bash
pytest -q
node --check app/static/js/admin-tabs.js
```
