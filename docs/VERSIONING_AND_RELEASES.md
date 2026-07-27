# Versioning and automated releases

Dashboard Matrix keeps one human-facing version and one Python package version in
sync.

Examples:

| Display / Git tag | Python package |
|---|---|
| `0.1.0-beta.1` | `0.1.0b1` |
| `0.1.0` | `0.1.0` |

The synchronized files are:

- `VERSION`
- `version.json`
- `app/version.py`
- `pyproject.toml`
- `README.md`
- `CHANGELOG.md`

## Merge-driven version roll

`.github/workflows/version-bump.yml` runs after every pull request is merged into
`main`. If no version label is present, it increments the beta serial:

```text
0.1.0-beta.1 -> 0.1.0-beta.2
```

Optional labels change the roll behavior:

| Pull request label | Result |
|---|---|
| `version:beta` | Increment beta serial; this is the default |
| `version:patch` | Increment patch and begin at `beta.1` |
| `version:minor` | Increment minor and begin at `beta.1` |
| `version:major` | Increment major and begin at `beta.1` |
| `version:stable` | Remove the prerelease suffix from the current base version |

Run **Create version labels** once from the Actions page to create or update these
labels.

The version workflow performs these steps:

1. Checks out the latest `main` branch.
2. Selects the version roll from the merged PR labels.
3. Runs `scripts/bump_version.py`.
4. Compiles Python and runs the complete test suite.
5. Commits the synchronized version files.
6. Creates an annotated `v<version>` tag.
7. Pushes the commit and tag.
8. Dispatches the release workflow for that exact tag.

## Repository settings

Under **Settings -> Actions -> General -> Workflow permissions**, select:

```text
Read and write permissions
```

The release bot must be allowed to push its version-only commit to `main`. If a
branch ruleset blocks all direct pushes, add a bypass for GitHub Actions or use a
maintainer-controlled release bot token in a customized checkout step.

The version workflow uses `pull_request_target` only for the closed/merged event
and checks out the trusted `main` branch. Do not change it to check out an
unmerged contributor branch with a write token.

## Release artifacts

`.github/workflows/release.yml` validates the tag and publishes:

- Source ZIP
- Source TAR.GZ
- Python wheel
- Python source distribution
- Windows x64 executable ZIP
- Raspberry Pi install bundle
- SHA-256 checksum files

A prerelease suffix such as `-beta.2` automatically marks the GitHub release as a
prerelease. Stable versions create normal releases. GitHub-generated notes are
organized by `.github/release.yml`.

The build commit is written to `app/build_commit.txt` during packaging. The file
is included in built artifacts but ignored in the source repository. It allows
the nightly update channel to compare the installed build with the latest commit.

## Manual version operation

Preview the next version without changing files:

```bash
python scripts/bump_version.py --bump beta --print-only
```

Apply a local roll:

```bash
python scripts/bump_version.py \
  --bump patch \
  --pr-number 42 \
  --summary "Correct proxy header handling"
```

Normally the GitHub workflow should perform this operation so tags, artifacts,
and release notes remain consistent.

## Runtime update indicator

The background update checker uses the release channel selected in
Administration. The public endpoint:

```text
GET /api/updates/status
```

returns only the cached, non-sensitive status needed by the dashboard header.
The installed version is always shown in the header. The upward-arrow icon is
shown only when a newer version is available and links to the matching GitHub
release or nightly commit.
