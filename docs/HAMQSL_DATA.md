# HamQSL data collection

Dashboard Matrix 0.1 beta includes an internal background collector. No cron job or separate script is required.

The collector runs at application startup and every 600 seconds by default. It stores the last-known-good response in:

```text
data/hamqsl_solar.xml
```

Collector status is stored in:

```text
data/hamqsl_status.json
```

The interval can be changed before starting Dashboard Matrix:

```bash
export DASHBOARD_MATRIX_HAMQSL_INTERVAL=900
```

The minimum interval is 60 seconds. Ten minutes is recommended because HamQSL data does not need second-by-second polling.

If the tiles show an error, inspect:

```bash
cat data/hamqsl_status.json
```

Common causes include DNS failure, blocked outbound HTTPS, missing CA certificates, system clock errors, or temporary source unavailability.
