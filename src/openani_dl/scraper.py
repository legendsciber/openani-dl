import re
from typing import Optional

from bs4 import BeautifulSoup

from openani_dl.models import AnimeData, PageData


def _js2json(text: str) -> str:
    text = re.sub(r'\bvoid\s+0\b', 'null', text)
    return text


def parse_page(html: str) -> PageData:
    user = None
    popular_animes = []
    random_cdn_host = ""
    token = None
    refresh_token = None

    soup = BeautifulSoup(html, "lxml")
    for script in soup.find_all("script"):
        text = script.string or ""

        if "random_cdn_host" in text:
            host_match = re.search(r'random_cdn_host\s*:\s*"([^"]+)"', text)
            user_match = re.search(r'user\s*:\s*(\{[^}]+?\})', text)
            token_match = re.search(r'token\s*:\s*(\w+|null)', text)
            refresh_match = re.search(r'refreshToken\s*:\s*(\w+|null)', text)

            if host_match:
                random_cdn_host = host_match.group(1)

            if token_match and token_match.group(1) not in ("null", "void 0"):
                token = token_match.group(1)
            if refresh_match and refresh_match.group(1) not in ("null", "void 0"):
                refresh_token = refresh_match.group(1)

    return PageData(
        random_cdn_host=random_cdn_host,
        token=token,
        refresh_token=refresh_token,
        user=user,
        popular_animes=popular_animes,
    )


def extract_video_files(html: str, slug: str = "", season: str = "") -> list[dict]:
    files = []

    cdn_link = None
    cdn_match = re.search(r'CDN_LINK\s*:\s*"([^"]+)"', html)
    if cdn_match:
        cdn_link = cdn_match.group(1)

    if not slug:
        slug_match = re.search(r'slug:\s*"([^"]+)"', html[10000:20000])
        if slug_match:
            slug = slug_match.group(1)

    if not season:
        season_match = re.search(r'episodeData:.*?episodeNumber:\s*(\d+).*?(?=})', html, re.DOTALL)
        if not season_match:
            season_match = re.search(r'season:\s*(\d+)', html)

    # Find the files array specifically: files:[{resolution:...,file:"...",...},...]
    files_block = re.search(r'files\s*:\s*\[([^\]]+)\]', html)
    if files_block:
        files_raw = re.findall(
            r'resolution:\s*(\d+),\s*file:\s*"([^"]+)"',
            files_block.group(1),
        )
        for resolution, filename in files_raw:
            files.append({
                "resolution": int(resolution),
                "filename": filename,
            })

    if cdn_link and files:
        for f in files:
            if slug and season:
                f["url"] = f"{cdn_link.rstrip('/')}/{slug}/{season}/{f['filename']}"
            else:
                f["url"] = cdn_link.rstrip("/") + "/" + f["filename"]

    return files


def extract_anime_data(html: str) -> AnimeData | None:
    slug = None
    cdn_host = None

    slug_match = re.search(r'"slug":\s*"([^"]+)"', html)
    if not slug_match:
        slug_match = re.search(r'slug:\s*"([^"]+)"', html[10000:20000])
    if slug_match:
        slug = slug_match.group(1)

    cdn_match = re.search(r'CDN_LINK\s*:\s*"([^"]+)"', html)
    if cdn_match:
        cdn_link = cdn_match.group(1)
    else:
        host_match = re.search(r'random_cdn_host\s*:\s*"([^"]+)"', html)
        if host_match:
            cdn_link = host_match.group(1) + "/animes/"

    if slug and cdn_link:
        return AnimeData(
            slug=slug,
            cdn_link=cdn_link,
            download_link=cdn_link,
        )
    return None


def extract_episode_info(html: str) -> Optional[dict]:
    result = {}
    slug_match = re.search(r'"slug":\s*"([^"]+)"', html)
    if not slug_match:
        slug_match = re.search(r'slug:\s*"([^"]+)"', html[10000:20000])
    if slug_match:
        result["slug"] = slug_match.group(1)
    season_match = re.search(r'"season":\s*(\d+)', html)
    if season_match:
        result["season"] = int(season_match.group(1))
    episode_match = re.search(r'"episode":\s*(\d+)', html)
    if episode_match:
        result["episode"] = int(episode_match.group(1))
    title_match = re.search(r'"english":\s*"([^"]+)"', html)
    if title_match:
        result["title"] = title_match.group(1)
    return result if result else None



