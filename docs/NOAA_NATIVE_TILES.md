# NOAA Native Space-Weather Tiles

The NOAA Space Weather plugin uses official data from `services.swpc.noaa.gov`. It does not embed `www.spaceweather.gov`, which may refuse iframe connections.

Available widgets:

- Space Weather Summary
- Planetary Kp and Forecast
- NOAA Storm Scales
- Real-Time Solar Wind
- GOES X-Ray Flux
- SWPC Alerts

Open **Admin → Plugin SDK & installed plugins**, locate **NOAA Space Weather**, enable it, select a destination dashboard, and choose **Add** for each desired widget.

Shared plugin settings may include:

```json
{
  "alert_limit": 5
}
```

The parser accepts both NOAA products represented as a header row followed by array rows and newer products represented as arrays of JSON objects.
