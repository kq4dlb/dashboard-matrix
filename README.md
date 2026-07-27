# KQ4DLB Dashboard Matrix

**Version 0.1.0-beta.1**

Dashboard Matrix is a lightweight, self-hosted dashboard platform created by
Marc Smith (KQ4DLB). It combines configurable dashboards, movable and resizable
cards, controlled iframe proxying, scripts, plugins, map providers, themes, and
shareable layouts in one independent open-source project.

## 0.1 beta highlights

- First-run setup wizard
- Blank, Amateur Radio, and Home Lab starter templates
- Multiple dashboards, card rotation, layout mode, locking, and title controls
- Layout import analysis with rename, replace, merge, and skip strategies
- Layout export, optional screenshot preview, and direct GitHub publishing
- Dashboard Matrix Exchange repository template
- Controlled proxy sources with per-source diagnostics
- Plugin permission approvals and environment-variable secret mappings
- General map-provider SDK with DX Cluster as a separate provider
- Theme package SDK with Matrix Light as the default and Matrix Dark for low-light use
- Stable, beta, and nightly update channels
- Header version display with a GitHub update-available indicator
- Automatic version roll, tagging, release notes, and release artifacts after each merge
- Docker, Linux, Windows executable, and Raspberry Pi automation
- Automatic startup after reboot on Linux, Raspberry Pi, Windows, and Docker
- Tabbed Administration workspace with keyboard navigation and remembered sections

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python matrix.py
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python matrix.py
```

Open `http://127.0.0.1:8080/setup` and complete the first-run wizard.


## Install with automatic startup

Linux and Raspberry Pi installers enable Dashboard Matrix at boot by default:

```bash
sudo ./scripts/install.sh
# Raspberry Pi OS
sudo ./scripts/install-raspberry-pi.sh
```

Windows installs an at-startup Scheduled Task, and Docker Compose uses
`restart: unless-stopped`. Manage or disable startup with the included
platform scripts. See [Automatic startup](docs/AUTOSTART.md).

## Docker

```bash
docker compose up -d --build
```

Set strong values for:

```text
DASHBOARD_MATRIX_ADMIN_PASSWORD
DASHBOARD_MATRIX_SESSION_SECRET
```

The first-run wizard replaces the initial administrator password.

## Screenshots

Screenshot preview is optional:

```bash
pip install '.[screenshots]'
playwright install chromium
```

## Layout publishing

The Admin interface can download an export and optionally publish the same JSON
and screenshot to a GitHub repository. Set a token for server-side publishing:

```text
DASHBOARD_MATRIX_LAYOUT_GITHUB_TOKEN
```

The token is never stored in SQLite. Repository, branch, and folder settings are
stored; a token entered in the browser is used only for that request.

See [Exchange repository design](docs/EXCHANGE_REPOSITORY.md).

## Optional station integrations

```bash
pip install '.[station]'
```

## Documentation

- [Administration interface](docs/ADMINISTRATION.md)
- [Automatic startup](docs/AUTOSTART.md)
- [Beta testing](docs/BETA_TESTING.md)
- [Layout sharing](docs/LAYOUT_SHARING.md)
- [Exchange repository](docs/EXCHANGE_REPOSITORY.md)
- [Plugin SDK](docs/PLUGIN_SDK.md)
- [Plugin security](docs/PLUGIN_SECURITY.md)
- [Map-provider SDK](docs/MAP_PROVIDER_SDK.md)
- [Theme SDK](docs/THEME_SDK.md)
- [Station integrations](docs/STATION_INTEGRATIONS.md)

## Versioning and releases

Every pull request merged into `main` automatically rolls the version, runs the
test suite, creates a version tag, and starts the release build. The default
behavior increments the beta serial; version labels can request patch, minor,
major, or stable releases.

See [Versioning and automated releases](docs/VERSIONING_AND_RELEASES.md).

## License

Dashboard Matrix is released under the MIT License.
