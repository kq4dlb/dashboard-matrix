from scripts.bump_version import DisplayVersion, next_version


def test_beta_roll_increments_serial():
    current = DisplayVersion.parse("0.1.0-beta.1")
    result = next_version(current, "beta")
    assert result.display() == "0.1.0-beta.2"
    assert result.package() == "0.1.0b2"


def test_base_rolls_restart_beta_serial():
    current = DisplayVersion.parse("0.1.4-beta.7")
    assert next_version(current, "patch").display() == "0.1.5-beta.1"
    assert next_version(current, "minor").display() == "0.2.0-beta.1"
    assert next_version(current, "major").display() == "1.0.0-beta.1"


def test_stable_promotion_removes_prerelease():
    current = DisplayVersion.parse("0.2.0-beta.9")
    result = next_version(current, "stable")
    assert result.display() == "0.2.0"
    assert result.package() == "0.2.0"


def test_beta_without_serial_normalizes_to_next_serial():
    current = DisplayVersion.parse("0.1.0-beta")
    assert next_version(current, "beta").display() == "0.1.0-beta.1"


def test_repository_version_files_are_synchronized():
    import json
    import tomllib
    from pathlib import Path

    from app.version import APP_VERSION, PACKAGE_VERSION

    root = Path(__file__).resolve().parents[1]
    assert (root / "VERSION").read_text(encoding="utf-8").strip() == APP_VERSION
    metadata = json.loads((root / "version.json").read_text(encoding="utf-8"))
    assert metadata["version"] == APP_VERSION
    assert metadata["package_version"] == PACKAGE_VERSION
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == PACKAGE_VERSION
