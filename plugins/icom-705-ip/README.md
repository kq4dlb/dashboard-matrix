# Icom IC-705 over IP plugin

This plugin connects directly to the IC-705 WLAN Remote service. It does not use a serial device and does not require Hamlib `rigctld`.

## Radio setup

On the IC-705:

1. Enable **Network Control** under the WLAN Remote settings.
2. Configure a Remote username and password.
3. Use control UDP port `50001` unless you deliberately changed it.
4. Confirm the CI-V address is `A4`.
5. Give the radio a DHCP reservation or static address.

## Linux dependency

RigPlane requires Python 3.11 or newer. Install it into the same virtual environment used to start Dashboard Matrix:

```bash
sudo apt-get update
sudo apt-get install -y libopus0 libportaudio2
/opt/dashboard-matrix/.venv/bin/pip install 'rigplane>=2.11,<3.0'
```

For a source installation, replace `/opt/dashboard-matrix/.venv/bin/pip` with the virtual environment used by your startup script.

## Admin configuration

Open **Admin → Extensions → Plugin SDK and installed plugins → Icom IC-705 over IP**.

Enable the plugin and approve:

- `local-network`
- `secrets`

Paste this into **Shared settings JSON**:

```json
{
  "host": "192.168.1.125",
  "username": "KQ4DLB",
  "control_port": 50001,
  "radio_address": "0xA4",
  "poll_interval": 1.5,
  "command_timeout": 2.0,
  "reconnect_delay": 3.0,
  "stale_after": 8.0,
  "max_watts": 10
}
```

The IP address and username are stored in the Dashboard Matrix SQLite database. The actual radio password is kept outside SQLite.

## Password mapping options

In the Admin **Secret mappings** section, map `password` using one of these methods.

### Option A: environment variable

Enter this in the Admin mapping field:

```text
ICOM_705_REMOTE_PASSWORD
```

The full-sync plugin manager resolves that variable from:

1. The running Dashboard Matrix process environment.
2. The file named by `DASHBOARD_MATRIX_ENV_FILE`.
3. `/etc/dashboard-matrix.env`.
4. `.env` in the Dashboard Matrix application directory.
5. `dashboard-matrix.env` in the application directory.

Example `/etc/dashboard-matrix.env` entry:

```dotenv
ICOM_705_REMOTE_PASSWORD='replace-with-radio-password'
```

### Option B: password file

Create a password file readable by the Dashboard Matrix process:

```bash
sudo install -d -m 0750 -o dashboard-matrix -g dashboard-matrix /var/lib/dashboard-matrix/secrets
printf '%s' 'replace-with-radio-password' | sudo tee /var/lib/dashboard-matrix/secrets/icom705-password >/dev/null
sudo chown dashboard-matrix:dashboard-matrix /var/lib/dashboard-matrix/secrets/icom705-password
sudo chmod 0600 /var/lib/dashboard-matrix/secrets/icom705-password
```

Enter this in the Admin mapping field:

```text
file:/var/lib/dashboard-matrix/secrets/icom705-password
```

The password-file method works with systemd and custom startup scripts because the plugin manager reads the file directly before launching the isolated plugin worker.

## Shared polling

The plugin uses one persistent worker and one background radio connection. Every IC-705 card reads the same cached snapshot, so separate cards do not compete for the radio connection.

## First-release behavior

- Read-only radio monitoring.
- Automatic reconnect after radio or Wi-Fi interruptions.
- Settings changes restart only the IC-705 connection.
- RF wattage is estimated from the configured maximum output.
