# Dashboard Matrix version automation patch

This patch is based on the current Dashboard Matrix 0.1 beta source and sets the
application display version to `0.1.0-beta.1`.

## Apply

```bash
unzip dashboard-matrix-version-automation-patch.zip
cp -a dashboard-matrix-version-automation-patch/. /path/to/dashboard-matrix/
cd /path/to/dashboard-matrix
pytest -q
```

## GitHub setup

1. Push these files through a pull request.
2. In **Settings -> Actions -> General**, grant workflows read/write permission.
3. Make sure the version workflow can push its version-only commit to `main`.
4. Run **Create version labels** once from the Actions tab.
5. Future merged pull requests default to beta serial increments.

The next unlabeled merge after this patch will roll `0.1.0-beta.1` to
`0.1.0-beta.2`, create tag `v0.1.0-beta.2`, and dispatch the release build.
