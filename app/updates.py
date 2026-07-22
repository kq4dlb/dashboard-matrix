from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Literal

from packaging.version import InvalidVersion, Version

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_admin
from app.database import connection, get_setting, set_setting
from app.version import APP_VERSION, DEFAULT_UPDATE_REPOSITORY

router = APIRouter(prefix="/api/updates", tags=["updates"])

CHANNELS = {"stable", "beta", "nightly"}
CHECK_INTERVAL_SECONDS = 24 * 60 * 60


class UpdateSettings(BaseModel):
    repository: str = Field(
        default=DEFAULT_UPDATE_REPOSITORY,
        pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
    )
    channel: Literal["stable", "beta", "nightly"] = "beta"
    automatic_checks: bool = True


def _request_json(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"Dashboard-Matrix/{APP_VERSION} update-checker",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub returned HTTP {exc.code}: {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Unable to reach GitHub: {exc.reason}") from exc


def _version(value: str) -> Version:
    cleaned = value.strip().lower().lstrip("v")
    try:
        return Version(cleaned)
    except InvalidVersion as exc:
        raise RuntimeError(f"GitHub returned an invalid release version: {value}") from exc


def _release_candidate(repository: str, channel: str) -> dict[str, Any]:
    if channel == "nightly":
        commits = _request_json(
            f"https://api.github.com/repos/{repository}/commits?per_page=1"
        )
        if not isinstance(commits, list) or not commits:
            raise RuntimeError("GitHub returned no commits")
        commit = commits[0]
        sha = str(commit.get("sha", ""))
        date = (
            commit.get("commit", {})
            .get("committer", {})
            .get("date", "")
        )
        return {
            "version": f"nightly-{sha[:7]}",
            "url": commit.get("html_url", ""),
            "published_at": date,
            "prerelease": True,
            "nightly_sha": sha,
        }

    releases = _request_json(
        f"https://api.github.com/repos/{repository}/releases?per_page=30"
    )
    if not isinstance(releases, list):
        raise RuntimeError("GitHub returned an invalid releases response")
    for release in releases:
        if release.get("draft"):
            continue
        if channel == "stable" and release.get("prerelease"):
            continue
        return {
            "version": str(release.get("tag_name") or release.get("name") or ""),
            "url": str(release.get("html_url") or ""),
            "published_at": str(release.get("published_at") or ""),
            "prerelease": bool(release.get("prerelease")),
            "notes": str(release.get("body") or "")[:4000],
        }
    raise RuntimeError(f"No {channel} release is available")


def read_settings() -> dict[str, Any]:
    with connection() as conn:
        return {
            "repository": get_setting(
                conn,
                "update_repository",
                DEFAULT_UPDATE_REPOSITORY,
            ),
            "channel": get_setting(conn, "release_channel", "beta"),
            "automatic_checks": get_setting(
                conn,
                "automatic_update_checks",
                "1",
            ) == "1",
        }


def check_for_updates() -> dict[str, Any]:
    settings = read_settings()
    channel = settings["channel"]
    repository = settings["repository"]
    candidate = _release_candidate(repository, channel)

    if channel == "nightly":
        latest = candidate["version"]
        update_available = True
        message = "A newer nightly commit may be available. Review the commit before installing."
    else:
        latest = candidate["version"]
        update_available = _version(latest) > _version(APP_VERSION)
        message = (
            f"Dashboard Matrix {latest} is available."
            if update_available
            else "This installation is current for the selected release channel."
        )

    result = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "channel": channel,
        "repository": repository,
        "current_version": APP_VERSION,
        "latest_version": latest,
        "update_available": update_available,
        "release_url": candidate.get("url", ""),
        "published_at": candidate.get("published_at", ""),
        "message": message,
        "notes": candidate.get("notes", ""),
    }
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO update_checks(
                id,checked_at,channel,current_version,latest_version,
                update_available,release_url,message
            ) VALUES(1,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                checked_at=excluded.checked_at,
                channel=excluded.channel,
                current_version=excluded.current_version,
                latest_version=excluded.latest_version,
                update_available=excluded.update_available,
                release_url=excluded.release_url,
                message=excluded.message
            """,
            (
                result["checked_at"],
                channel,
                APP_VERSION,
                latest,
                int(update_available),
                result["release_url"],
                message,
            ),
        )
    return result


@router.get("/settings")
def get_update_settings(_: None = Depends(require_admin)) -> dict[str, Any]:
    settings = read_settings()
    with connection() as conn:
        row = conn.execute("SELECT * FROM update_checks WHERE id=1").fetchone()
    settings["last_check"] = dict(row) if row else None
    if settings["last_check"]:
        settings["last_check"]["update_available"] = bool(
            settings["last_check"]["update_available"]
        )
    return settings


@router.put("/settings")
def save_update_settings(
    item: UpdateSettings,
    _: None = Depends(require_admin),
) -> dict[str, Any]:
    with connection() as conn:
        set_setting(conn, "update_repository", item.repository)
        set_setting(conn, "release_channel", item.channel)
        set_setting(
            conn,
            "automatic_update_checks",
            "1" if item.automatic_checks else "0",
        )
    return item.model_dump()


@router.post("/check")
def manual_update_check(_: None = Depends(require_admin)) -> dict[str, Any]:
    try:
        return check_for_updates()
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc


async def update_check_loop() -> None:
    while True:
        settings = read_settings()
        if settings["automatic_checks"] and not os.getenv(
            "DASHBOARD_MATRIX_DISABLE_UPDATE_CHECKS"
        ):
            try:
                await asyncio.to_thread(check_for_updates)
            except Exception:
                pass
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
