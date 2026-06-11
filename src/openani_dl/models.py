from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EpisodeInfo:
    slug: str
    season: int
    episode: int
    title: str
    anime_title: str


@dataclass
class PageData:
    random_cdn_host: str
    token: Optional[str]
    refresh_token: Optional[str]
    user: Optional[dict]
    popular_animes: list[dict] = field(default_factory=list)


@dataclass
class AnimeData:
    slug: str
    cdn_link: str
    download_link: str
    seasons: list[dict] = field(default_factory=list)
    fansubs: list[dict] = field(default_factory=list)
    skiptimes: dict = field(default_factory=dict)
    tracks: dict = field(default_factory=dict)


@dataclass
class AnisubPackage:
    id: str
    name: str
    fansub_id: str
    resolutions: list[str]
    audio: str
    subtitle: str


@dataclass
class VideoSource:
    url: str
    referer: str
    subtitle_url: Optional[str] = None
    quality: Optional[str] = None
