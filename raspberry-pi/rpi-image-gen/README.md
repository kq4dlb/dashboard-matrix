# Raspberry Pi image automation

Dashboard Matrix provides two Raspberry Pi paths:

1. `scripts/install-raspberry-pi.sh` installs the application on an existing
   64-bit Raspberry Pi OS system and enables its systemd service.
2. `scripts/build-raspberry-pi-image.sh` builds a base image with Raspberry Pi's
   `rpi-image-gen`, customizes it with `virt-customize`, installs Dashboard
   Matrix, and emits a compressed image plus SHA-256 checksum.

The full-image workflow is disabled unless the repository variable
`ENABLE_RPI_IMAGE_BUILD` is `true`. It requires a compatible self-hosted ARM64
runner, `rpi-image-gen` dependencies, and `libguestfs-tools`.

Useful repository variables:

```text
ENABLE_RPI_IMAGE_BUILD=true
RPI_IMAGE_GEN_HOME=/home/runner/rpi-image-gen
RPI_IMAGE_CONFIG=/home/runner/rpi-image-gen/config/trixie-minbase.yaml
```
