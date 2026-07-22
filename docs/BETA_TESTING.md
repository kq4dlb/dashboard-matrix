# Dashboard Matrix 0.1 beta testing

## Clean-install test

1. Start with an empty `DASHBOARD_MATRIX_DATA_DIR`.
2. Open `/setup`.
3. Test each starter template in a separate clean data directory.
4. Confirm the selected theme and release channel are retained.
5. Confirm the administrator password works and the setup page is no longer
   available after completion.

## Dashboard test

- Add, edit, delete, move, resize, lock, and refresh cards.
- Test dashboard rotation and pause/resume.
- Test title display modes on one-row and multi-row cards.
- Test station placeholders in URLs.

## Import/export test

- Export a layout locally.
- Capture a screenshot when Playwright is installed.
- Analyze the export before import.
- Exercise rename, replace, merge, and skip conflicts.
- Publish to a test Exchange repository with automatic publishing selected.

## Proxy test

- Configure only a source you are authorized to proxy.
- Run the Test action and review DNS, response code, frame headers, content type,
  redirects, and configured rewrites.
- Confirm unapproved hosts and private-address restrictions are enforced.

## Plugin test

- Review every declared permission before approval.
- Map required secret names to environment-variable names.
- Confirm secret values are not returned by the API or stored in the database.
- Confirm unapproved plugins cannot execute.
