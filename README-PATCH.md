# Dashboard Matrix autostart patch

Copy this directory over the repository root. It adds consistent automatic
startup after reboot for Linux, Raspberry Pi, Windows, and Docker, plus optional
Raspberry Pi kiosk launch and platform management scripts.

Validate with:

```bash
pytest -q
bash -n scripts/install.sh scripts/install-raspberry-pi.sh scripts/manage-autostart.sh scripts/kiosk.sh
```

The repository's merge-version workflow should create the next version after
this patch is merged; the patch does not manually change VERSION.
