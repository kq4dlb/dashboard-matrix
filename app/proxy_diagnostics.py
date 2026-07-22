from __future__ import annotations

import socket
import time
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_admin
from app.database import connection, row_to_dict
from app.proxy import _validate_target

router = APIRouter(prefix="/api/proxy-sources", tags=["proxy-diagnostics"])


@router.post("/{source_id}/test")
async def test_proxy_source(
    source_id: str,
    _: None = Depends(require_admin),
) -> dict:
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM proxy_sources WHERE source_id=?",
            (source_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Proxy source not found")
    source = row_to_dict(row) | {"source_id": row["source_id"]}
    target = source["base_url"]
    parsed = urlsplit(target)
    started = time.perf_counter()

    try:
        addresses = sorted(
            {
                item[4][0]
                for item in socket.getaddrinfo(
                    parsed.hostname,
                    parsed.port or (443 if parsed.scheme == "https" else 80),
                    type=socket.SOCK_STREAM,
                )
            }
        )
        _validate_target(target, source)
    except HTTPException as exc:
        return {
            "ok": False,
            "stage": "validation",
            "error": exc.detail,
            "target": target,
        }
    except OSError as exc:
        return {
            "ok": False,
            "stage": "dns",
            "error": str(exc),
            "target": target,
        }

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20.0, connect=10.0),
            follow_redirects=True,
            headers={"User-Agent": "Dashboard-Matrix/0.1 proxy-diagnostics"},
        ) as client:
            response = await client.head(target)
            if response.status_code in {400, 403, 405, 501}:
                response = await client.get(
                    target,
                    headers={"Range": "bytes=0-32767"},
                )
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "stage": "request",
            "error": str(exc),
            "target": target,
            "addresses": addresses,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
        }

    csp = response.headers.get("content-security-policy", "")
    xfo = response.headers.get("x-frame-options", "")
    notes: list[str] = []
    if xfo:
        notes.append(f"Upstream sends X-Frame-Options: {xfo}")
    if "frame-ancestors" in csp.lower():
        notes.append("Upstream CSP contains a frame-ancestors directive")
    if response.cookies:
        notes.append("Upstream uses cookies; authenticated pages may not work through the proxy")
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type.lower():
        notes.append("The base URL does not currently return HTML")

    return {
        "ok": response.status_code < 400,
        "stage": "complete",
        "target": target,
        "final_url": str(response.url),
        "status_code": response.status_code,
        "reason": response.reason_phrase,
        "addresses": addresses,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "content_type": content_type,
        "x_frame_options": xfo,
        "content_security_policy": csp[:1000],
        "configured_rewrites": {
            "strip_x_frame_options": source["strip_x_frame_options"],
            "strip_frame_ancestors": source["strip_frame_ancestors"],
            "inject_base_tag": source["inject_base_tag"],
        },
        "notes": notes,
        "proxy_preview": f"/proxy/{source_id}/",
    }
