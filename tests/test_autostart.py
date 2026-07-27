from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_systemd_service_is_boot_enabled_and_self_restarting():
    service = (ROOT / "systemd" / "dashboard-matrix.service").read_text()
    assert "WantedBy=multi-user.target" in service
    assert "Restart=always" in service
    assert "After=network-online.target" in service
    assert "ExecStartPre=/usr/bin/test -f /opt/dashboard-matrix/matrix.py" in service


def test_linux_install_enables_service_by_default():
    install = (ROOT / "scripts" / "install.sh").read_text()
    assert 'AUTOSTART="${DASHBOARD_MATRIX_AUTOSTART:-1}"' in install
    assert 'systemctl enable --now dashboard-matrix.service' in install
    assert "--no-autostart" in install


def test_raspberry_pi_installer_supports_server_and_optional_kiosk_autostart():
    install = (ROOT / "scripts" / "install-raspberry-pi.sh").read_text()
    assert 'AUTOSTART="${DASHBOARD_MATRIX_AUTOSTART:-1}"' in install
    assert 'systemctl enable --now dashboard-matrix.service' in install
    assert "--kiosk-user" in install
    assert "dashboard-matrix-kiosk.desktop" in install


def test_windows_installer_uses_at_startup_task():
    install = (ROOT / "scripts" / "install-windows.ps1").read_text()
    assert 'New-ScheduledTaskTrigger -AtStartup' in install
    assert '$Autostart' in install
    assert 'DASHBOARD_MATRIX_AUTOSTART' in install


def test_compose_has_restart_policy():
    compose = (ROOT / "docker-compose.yml").read_text()
    assert "restart: unless-stopped" in compose
