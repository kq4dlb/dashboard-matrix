# Dashboard Matrix Station Integrations

Dashboard Matrix 0.1 beta adds starter connectors for Hamlib rigctld, WSJT-X, MQTT, APRS.fi and Meshtastic. Enable plugins and configure shared settings in **Admin → Plugin SDK & installed plugins**.

## Hamlib rigctld
Start rigctld for the radio, normally on TCP 4532. Configure `host`, `port`, and `timeout`. The plugin uses read-only Hamlib commands and does not change the radio.

## WSJT-X
In WSJT-X, set UDP server to the Dashboard Matrix host and port 2237. Run `scripts/wsjtx_listener.py`, or install the included `systemd/dashboard-matrix-wsjtx-listener.service`. The listener writes the newest Status packet to `data/wsjtx_status.json`.

## MQTT
Install `requirements-optional.txt`, then configure broker host, port, credentials and a topic. The first release performs a short-lived subscription each refresh; a persistent broker service is planned for a later release.

## APRS.fi
Create an APRS.fi API key, configure it as `api_key`, and optionally override `callsign`. The shared Dashboard Matrix callsign is used by default.

## Meshtastic
Install optional dependencies, configure a serial port such as `/dev/ttyUSB0`, and ensure the Dashboard Matrix service account can access it. On Linux this usually means membership in the `dialout` group.

## Security
Treat plugin credentials as secrets. Dashboard Matrix currently stores plugin settings in SQLite. Use host filesystem permissions, restrict Admin access, and avoid exposing the Admin interface directly to the public internet.
