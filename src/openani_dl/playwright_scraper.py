from __future__ import annotations

import asyncio
import json
import re
from typing import Optional

from openani_dl.models import VideoSource

BASE_URL = "https://openani.me"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"


class PlaywrightScraper:
    """Playwright-based scraper for JavaScript-rendered pages."""

    def __init__(self):
        self._playwright = None
        self._browser = None

    async def __aenter__(self):
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        return self

    async def __aexit__(self, *args):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def find_video_source(
        self,
        slug: str,
        season: int,
        episode: int,
    ) -> Optional[VideoSource]:
        url = f"{BASE_URL}/anime/{slug}/{season}/{episode}"
        m3u8_urls = []
        video_urls = []

        context = await self._browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 720},
            java_script_enabled=True,
        )

        page = await context.new_page()

        async def on_response(response):
            if response.status != 200:
                return
            url_lower = response.url.lower()
            if ".m3u8" in url_lower:
                body = await response.body()
                m3u8_urls.append({"url": response.url, "body": body.decode("utf-8", errors="replace")[:500]})
            elif url_lower.endswith(".ts") or url_lower.endswith(".mp4"):
                video_urls.append(response.url)

        page.on("response", on_response)

        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)

        # Try to get the video source from the page
        video_src = await page.evaluate("""
            () => {
                const video = document.querySelector('video');
                if (video) {
                    const src = video.src || video.currentSrc;
                    if (src && src.startsWith('http')) return src;
                }
                // Check for HLS.js or video.js instances
                if (window.hls) {
                    return window.hls.url || null;
                }
                // Check for player instances
                for (const key of Object.keys(window)) {
                    try {
                        const val = window[key];
                        if (val && val.constructor && val.constructor.name === 'Hls') {
                            return val.url || null;
                        }
                    } catch(e) {}
                }
                return null;
            }
        """)

        await context.close()

        if video_src:
            return VideoSource(url=video_src, referer=BASE_URL)

        if m3u8_urls:
            best = max(
                m3u8_urls,
                key=lambda x: "master" in x["url"] or "index" in x["url"],
            )
            return VideoSource(url=best["url"], referer=BASE_URL)

        return None

    async def get_cdn_host(self, slug: str, season: int, episode: int) -> Optional[str]:
        """Try to extract the resolved CDN host from a real browser session."""
        url = f"{BASE_URL}/anime/{slug}/{season}/{episode}"

        context = await self._browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 720},
        )

        page = await context.new_page()

        # Intercept network requests to find API calls
        api_calls = []

        async def on_request(request):
            if "api.openani.me" in request.url or "kms.openani.me" in request.url:
                api_calls.append({
                    "url": request.url,
                    "method": request.method,
                    "headers": dict(request.headers),
                })

        page.on("request", on_request)

        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)

        # Get the page's CDN data from the embedded context
        cdn_host = await page.evaluate("""
            () => {
                const scripts = document.querySelectorAll('script');
                for (const s of scripts) {
                    if (s.text && s.text.includes('random_cdn_host')) {
                        const m = s.text.match(/random_cdn_host\\s*:\\s*"([^"]+)"/);
                        if (m) return m[1];
                    }
                }
                return null;
            }
        """)

        await context.close()

        return cdn_host


async def find_source_async(
    slug: str,
    season: int,
    episode: int,
) -> Optional[VideoSource]:
    async with PlaywrightScraper() as scraper:
        return await scraper.find_video_source(slug, season, episode)
