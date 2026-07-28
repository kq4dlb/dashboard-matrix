# Icom IC-705 over IP plugin

This plugin connects directly to the IC-705 Remote control service over Wi-Fi. It does not use a serial device and does not require Hamlib `rigctld`.

## Radio setup

On the IC-705, configure the WLAN Remote settings:

1. Enable **Network Control**.
2. Set the control UDP port to **50001**.
3. Leave the serial and audio UDP ports at **50002** and **50003** unless your network design requires different values.
4. Create or select a Remote username and password.
5. Confirm the radio CI-V address is **A4**.
6. Give the IC-705 a DHCP reservation or static address so the dashboard always finds the same radio.

Only the control port is entered in the plugin. RigPlane negotiates the remaining UDP streams with the radio.

## Dashboard setup

Install the optional dependency from the Dashboard Matrix repository:

```bash
python -m pip install -e '.[icom-ip]'
```

RigPlane requires Python 3.11 or newer.

For Docker Compose, add these values to `.env`, then rebuild the image:

```dotenv
DASHBOARD_MATRIX_INSTALL_ICOM_IP=1
ICOM_705_REMOTE_PASSWORD=replace-with-the-radio-password
```

```bash
docker compose build --no-cache
docker compose up -d
```

In **Admin → Plugins**:

1. Enable **Icom IC-705 over IP**.
2. Approve `local-network` and `secrets`.
3. Set the host, Remote username, control port, and CI-V address.
4. Map the plugin's `password` secret to `ICOM_705_REMOTE_PASSWORD` (or another environment variable containing the IC-705 Remote password).
5. Add one or more IC-705 cards to a dashboard.

This plugin opts into a persistent worker, so all cards backed by `plugin.py` share one long-lived worker and one background radio connection. Other plugins keep the existing one-process-per-render behavior unless they explicitly opt in. Card refreshes only read the latest cached snapshot.

## First-release behavior

- Read-only radio monitoring.
- Automatic reconnect after Wi-Fi or radio restarts.
- Settings changes restart only the IC-705 connection.
- RF wattage is an estimate based on the configured maximum output. Use `10` watts for external DC operation or `5` watts when that is the radio's available maximum.
