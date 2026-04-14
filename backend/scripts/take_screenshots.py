"""Take README screenshots of the production site.

Uses the Playwright Chromium that backend already has installed
(via `uv run playwright install chromium`). Launches a high-DPI
viewport so the PNGs look crisp on retina and on the GitHub README
viewer at half-scale.

Usage:
    cd backend
    uv run --active python scripts/take_screenshots.py

Writes to docs/screenshots/*.png. Commit the files to git.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

BASE = "https://modelprice.boxtech.icu"
OUT_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "screenshots"

DESKTOP = {"width": 1440, "height": 900}


async def wait_for_hydration(page) -> None:
    await page.wait_for_function(
        """() => {
            const el = document.querySelector('.v2-hero-title');
            return el && /\\d/.test(el.textContent || '');
        }""",
        timeout=30_000,
    )
    await page.wait_for_timeout(500)


async def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            # ── Dark theme run ─────────────────────────────
            ctx = await browser.new_context(
                viewport=DESKTOP,
                device_scale_factor=2,
                color_scheme="dark",
                locale="en-US",
            )
            page = await ctx.new_page()

            await page.goto(f"{BASE}/", wait_until="networkidle", timeout=30_000)
            await wait_for_hydration(page)
            await page.screenshot(path=OUT_DIR / "home-dark.png", full_page=False)
            print("✓ home-dark.png")

            # Click first row that mentions Claude Sonnet 4.5 → open drawer
            await page.evaluate(
                """() => {
                    const link = [...document.querySelectorAll('.v2-row')].find(r =>
                        r.textContent.toLowerCase().includes('claude sonnet 4.5')
                    );
                    if (link) link.click();
                }"""
            )
            await page.wait_for_selector(".v2-drawer", timeout=10_000)
            await page.wait_for_timeout(700)
            await page.screenshot(path=OUT_DIR / "drawer-dark.png", full_page=False)
            print("✓ drawer-dark.png")

            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)

            # Full-page entity view
            await page.goto(
                f"{BASE}/m/claude-sonnet-4-5",
                wait_until="networkidle",
                timeout=30_000,
            )
            await page.wait_for_selector(".v2-entity-page", timeout=10_000)
            await page.wait_for_timeout(700)
            await page.screenshot(
                path=OUT_DIR / "entity-page-dark.png", full_page=False
            )
            print("✓ entity-page-dark.png")

            # Compare page with 4 popular models
            await page.goto(
                f"{BASE}/compare/claude-sonnet-4-5,gpt-4o,gemini-2-5-pro,kimi-k2-5",
                wait_until="networkidle",
                timeout=30_000,
            )
            await page.wait_for_selector(".v2-compare-grid", timeout=10_000)
            await page.wait_for_timeout(700)
            await page.screenshot(path=OUT_DIR / "compare-dark.png", full_page=False)
            print("✓ compare-dark.png")

            # Command palette
            await page.goto(f"{BASE}/", wait_until="networkidle", timeout=30_000)
            await wait_for_hydration(page)
            await page.keyboard.press("Meta+k")
            await page.wait_for_selector(".v2-palette", timeout=5_000)
            await page.keyboard.type("claude", delay=40)
            await page.wait_for_timeout(500)
            await page.screenshot(
                path=OUT_DIR / "command-palette-dark.png", full_page=False
            )
            print("✓ command-palette-dark.png")
            await page.keyboard.press("Escape")

            await ctx.close()

            # ── Light theme run ────────────────────────────
            ctx_light = await browser.new_context(
                viewport=DESKTOP,
                device_scale_factor=2,
                color_scheme="light",
                locale="en-US",
            )
            page = await ctx_light.new_page()
            await page.goto(BASE, wait_until="domcontentloaded", timeout=30_000)
            await page.evaluate(
                "localStorage.setItem('model-price-v2:theme', 'light')"
            )
            await page.goto(f"{BASE}/", wait_until="networkidle", timeout=30_000)
            await wait_for_hydration(page)
            await page.screenshot(path=OUT_DIR / "home-light.png", full_page=False)
            print("✓ home-light.png")

            await page.goto(
                f"{BASE}/m/claude-sonnet-4-5",
                wait_until="networkidle",
                timeout=30_000,
            )
            await page.wait_for_selector(".v2-entity-page", timeout=10_000)
            await page.wait_for_timeout(700)
            await page.screenshot(
                path=OUT_DIR / "entity-page-light.png", full_page=False
            )
            print("✓ entity-page-light.png")

            await ctx_light.close()

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
