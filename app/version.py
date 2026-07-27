from __future__ import annotations

import os
import subprocess
from pathlib import Path

APP_VERSION = "0.1.0-beta.1"
PACKAGE_VERSION = "0.1.0b1"
PRODUCT_NAME = "Dashboard Matrix"
PRODUCT_FULL_NAME = "KQ4DLB Dashboard Matrix"
PRODUCT_AUTHOR = "Marc Smith (KQ4DLB)"
DEFAULT_UPDATE_REPOSITORY = "KQ4DLB/dashboard-matrix"
DEFAULT_EXCHANGE_REPOSITORY = "KQ4DLB/dashboard-matrix-exchange"


def _build_commit() -> str:
    configured = os.getenv("DASHBOARD_MATRIX_BUILD_COMMIT", "").strip()
    if configured:
        return configured

    packaged = Path(__file__).with_name("build_commit.txt")
    if packaged.exists():
        return packaged.read_text(encoding="utf-8").strip()

    repository = Path(__file__).resolve().parents[1]
    if (repository / ".git").exists():
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repository,
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            )
            return result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
    return ""


BUILD_COMMIT = _build_commit()
