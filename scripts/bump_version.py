#!/usr/bin/env python3
"""Synchronize Dashboard Matrix versions after a merge.

The display version uses SemVer-style prerelease labels, for example
``0.1.0-beta.2``. Python package metadata uses the equivalent PEP 440 form,
for example ``0.1.0b2``.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "app" / "version.py"
PYPROJECT_FILE = ROOT / "pyproject.toml"
README_FILE = ROOT / "README.md"
CHANGELOG_FILE = ROOT / "CHANGELOG.md"
PLAIN_VERSION_FILE = ROOT / "VERSION"
VERSION_JSON_FILE = ROOT / "version.json"

DISPLAY_RE = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<stage>alpha|beta|rc)(?:\.(?P<serial>\d+))?)?$"
)


@dataclass(frozen=True)
class DisplayVersion:
    major: int
    minor: int
    patch: int
    stage: str | None = None
    serial: int | None = None

    @classmethod
    def parse(cls, value: str) -> "DisplayVersion":
        match = DISPLAY_RE.fullmatch(value.strip().lstrip("v"))
        if not match:
            raise ValueError(f"Unsupported Dashboard Matrix version: {value}")
        groups = match.groupdict()
        return cls(
            major=int(groups["major"]),
            minor=int(groups["minor"]),
            patch=int(groups["patch"]),
            stage=groups["stage"],
            serial=int(groups["serial"]) if groups["serial"] is not None else None,
        )

    def display(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        if not self.stage:
            return base
        serial = 0 if self.serial is None else self.serial
        return f"{base}-{self.stage}.{serial}"

    def package(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        if not self.stage:
            return base
        serial = 0 if self.serial is None else self.serial
        marker = {"alpha": "a", "beta": "b", "rc": "rc"}[self.stage]
        return f"{base}{marker}{serial}"


def current_version() -> DisplayVersion:
    text = VERSION_FILE.read_text(encoding="utf-8")
    match = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise RuntimeError("APP_VERSION was not found in app/version.py")
    return DisplayVersion.parse(match.group(1))


def next_version(current: DisplayVersion, bump: str) -> DisplayVersion:
    if bump == "stable":
        return DisplayVersion(current.major, current.minor, current.patch)
    if bump == "beta":
        if current.stage == "beta":
            serial = 0 if current.serial is None else current.serial
            return DisplayVersion(
                current.major,
                current.minor,
                current.patch,
                "beta",
                serial + 1,
            )
        if current.stage:
            return DisplayVersion(current.major, current.minor, current.patch, "beta", 1)
        return DisplayVersion(current.major, current.minor, current.patch + 1, "beta", 1)
    if bump == "patch":
        return DisplayVersion(current.major, current.minor, current.patch + 1, "beta", 1)
    if bump == "minor":
        return DisplayVersion(current.major, current.minor + 1, 0, "beta", 1)
    if bump == "major":
        return DisplayVersion(current.major + 1, 0, 0, "beta", 1)
    raise ValueError(f"Unknown bump type: {bump}")


def replace_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"Expected one version match in {path}, found {count}")
    path.write_text(updated, encoding="utf-8")


def prepend_changelog(version: str, *, pr_number: str, summary: str) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    text = CHANGELOG_FILE.read_text(encoding="utf-8") if CHANGELOG_FILE.exists() else "# Changelog\n"
    if not text.lstrip().startswith("# Changelog"):
        # Normalize older beta files that placed a release entry above the title.
        title_index = text.find("# Changelog")
        if title_index >= 0:
            text = text[title_index:]
        else:
            text = "# Changelog\n\n" + text
    entry_lines = [f"## {version} — {today}", ""]
    if pr_number:
        entry_lines.append(f"- Automated version roll after merge of PR #{pr_number}: {summary or 'merged changes'}.")
    else:
        entry_lines.append(f"- Automated version roll: {summary or 'merged changes'}.")
    entry = "\n".join(entry_lines) + "\n\n"
    marker = "# Changelog\n"
    text = text.replace(marker, marker + "\n" + entry, 1)
    CHANGELOG_FILE.write_text(text, encoding="utf-8")


def write_version_files(
    version: DisplayVersion,
    *,
    bump: str,
    pr_number: str,
    summary: str,
) -> None:
    display = version.display()
    package = version.package()
    replace_once(VERSION_FILE, r'^APP_VERSION\s*=\s*"[^"]+"', f'APP_VERSION = "{display}"')
    replace_once(VERSION_FILE, r'^PACKAGE_VERSION\s*=\s*"[^"]+"', f'PACKAGE_VERSION = "{package}"')
    replace_once(PYPROJECT_FILE, r'^version\s*=\s*"[^"]+"', f'version = "{package}"')
    replace_once(README_FILE, r'^\*\*Version [^*]+\*\*', f'**Version {display}**')
    PLAIN_VERSION_FILE.write_text(display + "\n", encoding="utf-8")
    VERSION_JSON_FILE.write_text(
        json.dumps(
            {
                "version": display,
                "package_version": package,
                "channel": version.stage or "stable",
                "bump": bump,
                "source_pr": int(pr_number) if pr_number.isdigit() else None,
                "summary": summary,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    prepend_changelog(display, pr_number=pr_number, summary=summary)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bump",
        choices=("beta", "patch", "minor", "major", "stable"),
        default="beta",
    )
    parser.add_argument("--pr-number", default="")
    parser.add_argument("--summary", default="")
    parser.add_argument("--print-only", action="store_true")
    args = parser.parse_args()

    current = current_version()
    upcoming = next_version(current, args.bump)
    if args.print_only:
        print(upcoming.display())
        return 0
    write_version_files(
        upcoming,
        bump=args.bump,
        pr_number=args.pr_number,
        summary=args.summary,
    )
    print(upcoming.display())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
