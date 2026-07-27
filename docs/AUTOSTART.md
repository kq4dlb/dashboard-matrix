# Automatic startup

Dashboard Matrix can start automatically whenever its host reboots.

## Linux and Raspberry Pi

The Linux and Raspberry Pi installers install a systemd service and enable it
by default:

```bash
sudo ./scripts/install.sh
# or
sudo ./scripts/install-raspberry-pi.sh
```

The installed service is `dashboard-matrix.service`. It starts after the
network-online target, runs under the dedicated `dashboard-matrix` account,
and automatically restarts if the process exits.

Manage it with:

```bash
sudo ./scripts/manage-autostart.sh status
sudo ./scripts/manage-autostart.sh enable
sudo ./scripts/manage-autostart.sh disable
sudo ./scripts/manage-autostart.sh restart
sudo ./scripts/manage-autostart.sh logs
```

To install without boot startup:

```bash
sudo ./scripts/install.sh --no-autostart
```

or:

```bash
sudo DASHBOARD_MATRIX_AUTOSTART=0 ./scripts/install-raspberry-pi.sh
```

## Optional Raspberry Pi kiosk

The Dashboard Matrix server runs headlessly by default. On a Raspberry Pi OS
Desktop installation, the installer can also add a desktop autostart entry that
opens Chromium in kiosk mode after the selected desktop user signs in:

```bash
sudo ./scripts/install-raspberry-pi.sh --kiosk-user pi
```

The Pi must be configured for desktop auto-login if the browser should appear
without anyone signing in. The server service itself does not require desktop
auto-login.

The kiosk URL can be overridden with:

```text
DASHBOARD_MATRIX_KIOSK_URL=http://127.0.0.1:8080/dashboard
```

## Windows

The Windows installer creates an elevated Scheduled Task named
`Dashboard Matrix` with an at-startup trigger. It runs as `SYSTEM`, starts
without an interactive login, and restarts after failures.

Manage it from Administrator PowerShell:

```powershell
.\scripts\manage-autostart.ps1 -Action Status
.\scripts\manage-autostart.ps1 -Action Enable
.\scripts\manage-autostart.ps1 -Action Disable
.\scripts\manage-autostart.ps1 -Action Restart
.\scripts\manage-autostart.ps1 -Action Logs
```

Set `DASHBOARD_MATRIX_AUTOSTART=0` before running the Windows installer to
install the application without registering the startup task.

## Docker

The supplied Compose file uses:

```yaml
restart: unless-stopped
```

The container therefore returns after the Docker daemon restarts unless an
administrator explicitly stopped it.

Verify the policy with:

```bash
docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' dashboard-matrix
```
