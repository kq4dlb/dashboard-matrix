from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app.auth import require_admin
from app.database import connection

router = APIRouter(prefix="/api/screenshots", tags=["screenshots"])


@router.get("/{slug}.png")
async def dashboard_screenshot(
    slug: str,
    request: Request,
    _: None = Depends(require_admin),
) -> Response:
    with connection() as conn:
        if not conn.execute(
            "SELECT 1 FROM dashboards WHERE slug=?",
            (slug,),
        ).fetchone():
            raise HTTPException(404, "Dashboard not found")

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise HTTPException(
            503,
            "Screenshot support is optional. Install playwright and run `playwright install chromium`.",
        ) from exc

    width = min(3840, max(800, int(os.getenv("DASHBOARD_MATRIX_SCREENSHOT_WIDTH", "1600"))))
    height = min(2160, max(600, int(os.getenv("DASHBOARD_MATRIX_SCREENSHOT_HEIGHT", "1000"))))
    base = str(request.base_url).rstrip("/")
    url = f"{base}/?slug={slug}&screenshot=1"
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
            )
            await page.goto(url, wait_until="networkidle", timeout=45000)
            await page.wait_for_selector("#dashboard-grid", timeout=15000)
            await page.wait_for_timeout(1500)
            image = await page.screenshot(full_page=True, type="png")
            await browser.close()
    except Exception as exc:
        raise HTTPException(502, f"Unable to capture dashboard screenshot: {exc}") from exc
    return Response(
        image,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )
