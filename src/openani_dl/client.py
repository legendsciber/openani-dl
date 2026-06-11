from __future__ import annotations

import json
import re
from typing import Optional

import httpx
from rich.console import Console

from openani_dl.models import AnimeData, PageData, VideoSource
from openani_dl.scraper import (
    extract_anime_data,
    extract_video_files,
    parse_page,
)

console = Console()

BASE_URL = "https://openani.me"
API_URL = "https://api.openani.me"
CLIENT_PROTOCOL = "RCSA-14402/05"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"


class OpenAnimeClient:
    def __init__(self, gateway_token: Optional[str] = None):
        self.gateway_token = gateway_token
        self._client = httpx.Client(
            follow_redirects=True,
            timeout=30,
            headers={"User-Agent": USER_AGENT},
        )

    def _headers(self) -> dict:
        h = {
            "Client-Protocol-Model": CLIENT_PROTOCOL,
            "User-Agent": USER_AGENT,
        }
        if self.gateway_token:
            h["Gateway-Token"] = self.gateway_token
        return h

    def fetch_page(self, url: str) -> str:
        response = self._client.get(url, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        return response.text

    def fetch_anime_page(self, slug: str, season: int = 1, episode: int = 1) -> str:
        url = f"{BASE_URL}/anime/{slug}/{season}/{episode}"
        return self.fetch_page(url)

    def api_get(self, path: str):
        url = f"{API_URL}{path}"
        try:
            response = self._client.get(url, headers=self._headers())
            if response.status_code == 200:
                ct = response.headers.get("content-type", "")
                if "json" in ct:
                    return response.json()
                text = response.text
                try:
                    return json.loads(text)
                except (json.JSONDecodeError, ValueError):
                    return text
            return None
        except httpx.HTTPError as e:
            console.print(f"[dim]API ({path}): {e}[/dim]")
            return None

    def get_anisub(self, slug: str) -> list | None:
        return self.api_get(f"/anime/{slug}/anisub")

    def extract_from_page_data(self, html: str, slug: str = "", season: str = "", quality: str = "best") -> Optional[VideoSource]:
        files = extract_video_files(html, slug=slug, season=season)

        if not files:
            return None

        files.sort(key=lambda x: x["resolution"], reverse=True)
        selected = None
        if quality != "best":
            q_val = int(quality.rstrip("p"))
            for f in files:
                if f["resolution"] <= q_val:
                    selected = f
                    break
        if not selected:
            selected = files[0]
        return VideoSource(
            url=selected["url"],
            referer=BASE_URL,
            quality=f'{selected["resolution"]}p',
        )

    def close(self):
        self._client.close()
