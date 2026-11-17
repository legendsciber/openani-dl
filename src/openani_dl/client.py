from __future__ import annotations

from urllib.parse import quote

import httpx

from openani_dl.models import EpisodeData, Fansub, VideoFile, VideoSource
from openani_dl.scraper import extract_cdn_link, extract_fansubs

BASE_URL = "https://openani.me"
API_URL = "https://api.openani.me"
CLIENT_PROTOCOL = "RCSA-14402/05"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
)

_TR_LOWER = str.maketrans(
    {
        "Ç": "c",
        "ç": "c",
        "Ğ": "g",
        "ğ": "g",
        "İ": "i",
        "ı": "i",
        "Ö": "o",
        "ö": "o",
        "Ş": "s",
        "ş": "s",
        "Ü": "u",
        "ü": "u",
    }
)


class OpenAnimeError(RuntimeError):
    pass


def _normalize(value: str) -> str:
    return value.translate(_TR_LOWER).casefold().strip()


def _find_fansub(fansubs: list[Fansub], query: str) -> Fansub:
    wanted = _normalize(query)
    if not wanted:
        raise OpenAnimeError("Fansub name cannot be empty.")

    for fansub in fansubs:
        candidates = (
            _normalize(fansub.id),
            _normalize(fansub.secure_name),
            _normalize(fansub.name),
        )
        if wanted in candidates:
            return fansub

    for fansub in fansubs:
        name = _normalize(fansub.name)
        secure_name = _normalize(fansub.secure_name)
        if name in wanted or wanted in name or secure_name in wanted:
            return fansub

    available = ", ".join(f"{f.name} ({f.secure_name})" for f in fansubs) or "none"
    raise OpenAnimeError(f'Fansub "{query}" not found. Available fansubs: {available}')


def _select_file(files: list[VideoFile], quality: str) -> VideoFile:
    ordered = sorted(files, key=lambda item: item.resolution)
    if not ordered:
        raise OpenAnimeError("No video files were returned for this episode.")

    value = (quality or "best").strip().lower()
    if value in ("best", "max"):
        return ordered[-1]

    value = value.removesuffix("p")
    if value == "4k":
        value = "2160"

    try:
        target = int(value)
    except ValueError as exc:
        raise OpenAnimeError(
            f'Invalid quality "{quality}". Use best or a resolution such as 2160, 1080, 720.'
        ) from exc

    candidates = [item for item in ordered if item.resolution <= target]
    if not candidates:
        available = ", ".join(f"{item.resolution}p" for item in ordered)
        raise OpenAnimeError(f"No file at or below {target}p. Available: {available}")
    return candidates[-1]


def _build_file_url(cdn_link: str, slug: str, season: int, filename: str) -> str:
    if filename.startswith(("http://", "https://")):
        return filename

    path, separator, query = filename.partition("?")
    url = f"{cdn_link.rstrip('/')}/{quote(slug)}/{season}/{path.lstrip('/')}"
    if separator:
        url += "?" + query
    return url


class OpenAnimeClient:
    def __init__(self) -> None:
        self._client = httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(30.0, read=120.0),
            headers={
                "User-Agent": USER_AGENT,
                "Client-Protocol-Model": CLIENT_PROTOCOL,
                "Origin": BASE_URL,
                "Referer": BASE_URL + "/",
            },
        )

    def fetch_page(self, slug: str, season: int, episode: int) -> str:
        url = f"{BASE_URL}/anime/{quote(slug)}/{season}/{episode}"
        try:
            response = self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OpenAnimeError(f"Could not load episode page: {exc}") from exc
        return response.text

    def _api_get(self, path: str) -> dict:
        try:
            response = self._client.get(f"{API_URL}{path}")
        except httpx.HTTPError as exc:
            raise OpenAnimeError(f"API request failed: {exc}") from exc

        if response.status_code != 200:
            detail = response.text.strip()
            if len(detail) > 200:
                detail = detail[:200] + "..."
            raise OpenAnimeError(
                f"API returned HTTP {response.status_code}: {detail or 'empty response'}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise OpenAnimeError("API returned invalid JSON.") from exc

        if not isinstance(payload, dict):
            raise OpenAnimeError("API returned an unexpected response.")
        return payload

    def _get_episode_payload(
        self,
        slug: str,
        season: int,
        episode: int,
        fansub_id: str | None,
    ) -> dict:
        path = f"/anime/{quote(slug)}/season/{season}/episode/{episode}"
        if fansub_id:
            path += f"?fansub={quote(str(fansub_id))}"
        return self._api_get(path)

    def get_episode_data(
        self,
        slug: str,
        season: int,
        episode: int,
        fansub: str | None = None,
        html: str | None = None,
    ) -> EpisodeData:
        html = html or self.fetch_page(slug, season, episode)

        cdn_link = extract_cdn_link(html)
        if not cdn_link:
            raise OpenAnimeError("Could not find the CDN link on the episode page.")

        selected = None
        if fansub:
            fansubs = extract_fansubs(html)
            if not fansubs:
                raise OpenAnimeError(
                    "Could not find the fansub list on the episode page."
                )
            selected = _find_fansub(fansubs, fansub)

        payload = self._get_episode_payload(
            slug,
            season,
            episode,
            selected.id if selected else None,
        )
        episode_data = payload.get("episodeData")
        if not isinstance(episode_data, dict):
            raise OpenAnimeError("API response does not contain episode data.")

        raw_fansub = episode_data.get("fansub") or {}
        returned_fansub = Fansub(
            id=str(raw_fansub.get("id", "")),
            name=str(raw_fansub.get("name", "Unknown")),
            secure_name=str(raw_fansub.get("secureName", "")),
            is_4k=bool(raw_fansub.get("is4K")),
        )
        if selected and returned_fansub.id and returned_fansub.id != selected.id:
            raise OpenAnimeError(
                f'API returned fansub "{returned_fansub.name}" instead of "{selected.name}".'
            )

        files: list[VideoFile] = []
        for item in episode_data.get("files") or []:
            if (
                not isinstance(item, dict)
                or "resolution" not in item
                or "file" not in item
            ):
                continue
            files.append(
                VideoFile(
                    resolution=int(item["resolution"]),
                    url=_build_file_url(cdn_link, slug, season, str(item["file"])),
                    size=int(item.get("size") or 0),
                )
            )
        if not files:
            raise OpenAnimeError("No video files were returned for this episode.")

        anime_meta = payload.get("animeMeta") or {}
        anime_title = (
            anime_meta.get("turkish")
            or anime_meta.get("english")
            or slug.replace("-", " ").title()
        )

        return EpisodeData(
            slug=slug,
            season=season,
            episode=episode,
            anime_title=str(anime_title),
            episode_title=str(episode_data.get("name") or f"Episode {episode}"),
            fansub=returned_fansub,
            files=files,
        )

    def resolve(
        self,
        slug: str,
        season: int,
        episode: int,
        quality: str = "best",
        fansub: str | None = None,
    ) -> VideoSource:
        data = self.get_episode_data(slug, season, episode, fansub=fansub)
        selected = _select_file(data.files, quality)
        return VideoSource(
            url=selected.url,
            referer=BASE_URL,
            resolution=selected.resolution,
            size=selected.size,
            fansub=data.fansub,
            anime_title=data.anime_title,
            episode_title=data.episode_title,
            season=season,
            episode=episode,
        )

    def close(self) -> None:
        self._client.close()
