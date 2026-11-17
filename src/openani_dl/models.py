from dataclasses import dataclass, field


@dataclass
class Fansub:
    id: str
    name: str
    secure_name: str
    is_4k: bool = False


@dataclass
class VideoFile:
    resolution: int
    url: str
    size: int = 0


@dataclass
class EpisodeData:
    slug: str
    season: int
    episode: int
    anime_title: str
    episode_title: str
    fansub: Fansub
    files: list[VideoFile] = field(default_factory=list)


@dataclass
class VideoSource:
    url: str
    referer: str
    resolution: int
    size: int
    fansub: Fansub
    anime_title: str
    episode_title: str
    season: int
    episode: int
