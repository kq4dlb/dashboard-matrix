from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import Response

from app.database import connection, row_to_dict

MAX_RESPONSE_BYTES = 15 * 1024 * 1024
MAX_REDIRECTS = 5
BLOCKED_REQUEST_HEADERS = {
    "host", "cookie", "authorization", "proxy-authorization", "connection",
    "content-length", "transfer-encoding", "upgrade", "origin", "referer",
}
PASSTHROUGH_RESPONSE_HEADERS = {
    "content-type", "content-language", "cache-control", "expires", "last-modified", "etag",
    "content-security-policy", "content-security-policy-report-only",
}

@dataclass
class CacheEntry:
    expires_at: float
    status_code: int
    content: bytes
    headers: dict[str, str]

_CACHE: dict[str, CacheEntry] = {}
_CACHE_LOCK = asyncio.Lock()


def _public_ip(ip_text: str) -> bool:
    ip = ipaddress.ip_address(ip_text)
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
        or ip.is_reserved or ip.is_unspecified
    )


def _validate_hostname(hostname: str) -> None:
    lowered = hostname.rstrip(".").lower()
    if lowered in {"localhost", "localhost.localdomain"} or lowered.endswith(".local"):
        raise HTTPException(403, "Proxy target hostname is not allowed")
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise HTTPException(502, f"Unable to resolve proxy target: {exc}") from exc
    addresses = {item[4][0] for item in infos}
    if not addresses or any(not _public_ip(address) for address in addresses):
        raise HTTPException(403, "Proxy target resolves to a private or reserved address")


def _validate_target(url: str, source: dict) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(400, "Invalid proxy target URL")
    if parsed.scheme == "http" and not source.get("allow_http", False):
        raise HTTPException(403, "Plain HTTP is disabled for this proxy source")
    base = urlsplit(source["base_url"])
    if parsed.hostname.lower() != (base.hostname or "").lower():
        raise HTTPException(403, "Redirect left the configured proxy hostname")
    base_port = base.port or (443 if base.scheme == "https" else 80)
    target_port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if target_port != base_port:
        raise HTTPException(403, "Redirect changed the configured proxy port")
    _validate_hostname(parsed.hostname)


def _inject_base_tag(content: bytes, content_type: str, target_url: str) -> bytes:
    if "text/html" not in content_type.lower():
        return content
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return content
    base_tag = f'<base href="{target_url}">'
    if re.search(r"<base\b", text, flags=re.IGNORECASE):
        return content
    head = re.search(r"<head\b[^>]*>", text, flags=re.IGNORECASE)
    if head:
        text = text[:head.end()] + base_tag + text[head.end():]
    else:
        text = base_tag + text
    return text.encode("utf-8")


def _response_headers(remote: httpx.Response, source: dict) -> dict[str, str]:
    headers = {k: v for k, v in remote.headers.items() if k.lower() in PASSTHROUGH_RESPONSE_HEADERS}
    if source.get("strip_x_frame_options", True):
        headers.pop("x-frame-options", None)
    if source.get("strip_frame_ancestors", True):
        csp = remote.headers.get("content-security-policy")
        if csp:
            directives = [d.strip() for d in csp.split(";") if d.strip()]
            directives = [d for d in directives if not d.lower().startswith("frame-ancestors")]
            if directives:
                headers["content-security-policy"] = "; ".join(directives)
        report_only = remote.headers.get("content-security-policy-report-only")
        if report_only:
            directives = [d.strip() for d in report_only.split(";") if d.strip()]
            directives = [d for d in directives if not d.lower().startswith("frame-ancestors")]
            if directives:
                headers["content-security-policy-report-only"] = "; ".join(directives)
    headers.pop("set-cookie", None)
    return headers


def get_proxy_source(source_id: str) -> dict:
    with connection() as conn:
        row = conn.execute("SELECT * FROM proxy_sources WHERE source_id=?", (source_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Proxy source not found")
    source = row_to_dict(row) | {"source_id": row["source_id"]}
    if not source.get("enabled"):
        raise HTTPException(403, "Proxy source is disabled")
    return source


async def fetch_proxied(source_id: str, path: str, request: Request) -> Response:
    source = get_proxy_source(source_id)
    base_url = source["base_url"]
    target = urljoin(base_url, path or "")
    if request.url.query:
        target += ("&" if "?" in target else "?") + request.url.query
    _validate_target(target, source)

    cache_key = target
    cache_seconds = int(source.get("cache_seconds", 0))
    if cache_seconds > 0:
        async with _CACHE_LOCK:
            cached = _CACHE.get(cache_key)
            if cached and cached.expires_at > time.time():
                return Response(cached.content, cached.status_code, cached.headers)

    request_headers = {
        key: value for key, value in request.headers.items()
        if key.lower() not in BLOCKED_REQUEST_HEADERS
    }
    request_headers["user-agent"] = "Dashboard-Matrix-Proxy/1.0"
    request_headers["accept-encoding"] = "identity"

    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=10.0), follow_redirects=False) as client:
        remote: httpx.Response | None = None
        current = target
        for _ in range(MAX_REDIRECTS + 1):
            _validate_target(current, source)
            remote = await client.get(current, headers=request_headers)
            if remote.status_code not in {301, 302, 303, 307, 308}:
                break
            location = remote.headers.get("location")
            if not location:
                break
            current = urljoin(current, location)
        else:
            raise HTTPException(502, "Too many proxy redirects")

    if remote is None:
        raise HTTPException(502, "Proxy request failed")
    content = remote.content
    if len(content) > MAX_RESPONSE_BYTES:
        raise HTTPException(413, "Remote response is too large for the dashboard proxy")
    content_type = remote.headers.get("content-type", "application/octet-stream")
    if source.get("inject_base_tag", True):
        content = _inject_base_tag(content, content_type, str(remote.url))
    headers = _response_headers(remote, source)
    headers["x-dashboard-matrix-proxy-source"] = source_id
    headers["x-content-type-options"] = "nosniff"
    response = Response(content, remote.status_code, headers)

    if cache_seconds > 0 and remote.status_code == 200:
        async with _CACHE_LOCK:
            _CACHE[cache_key] = CacheEntry(time.time() + cache_seconds, remote.status_code, content, headers)
    return response
