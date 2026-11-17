from __future__ import annotations

import re
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from openani_dl.models import VideoSource

console = Console()

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
)
INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize(value: str) -> str:
    cleaned = INVALID_FILENAME.sub("_", value).strip(" .")
    return cleaned or "untitled"


def _extension(url: str) -> str:
    path = url.split("?", 1)[0]
    suffix = Path(path).suffix
    return suffix if suffix and len(suffix) <= 5 else ".mp4"


def download_episode(source: VideoSource, output_dir: str = ".") -> Path:
    anime_dir = Path(output_dir).expanduser() / _sanitize(source.anime_title)
    anime_dir.mkdir(parents=True, exist_ok=True)

    filename = (
        f"S{source.season:02d}E{source.episode:02d}"
        f" - {_sanitize(source.episode_title)}{_extension(source.url)}"
    )
    output_path = anime_dir / filename

    if output_path.exists():
        size = output_path.stat().st_size
        if not source.size or size == source.size:
            console.print(f"[yellow]Already exists:[/yellow] {output_path}")
            return output_path
        console.print(
            f"[yellow]File exists with a different size, skipping:[/yellow] {output_path}"
        )
        return output_path

    part_path = output_path.with_name(output_path.name + ".part")
    offset = part_path.stat().st_size if part_path.exists() else 0
    if source.size and offset > source.size:
        part_path.unlink()
        offset = 0
    if source.size and offset == source.size:
        part_path.replace(output_path)
        console.print(f"[green]Already downloaded:[/green] {output_path}")
        return output_path

    headers = {
        "User-Agent": USER_AGENT,
        "Referer": source.referer + "/",
        "Origin": source.referer,
        "Accept": "*/*",
    }
    if offset:
        headers["Range"] = f"bytes={offset}-"

    console.print(
        f"[cyan]Downloading:[/cyan] {source.anime_title} "
        f"S{source.season:02d}E{source.episode:02d} "
        f"({source.fansub.name}, {source.resolution}p)"
    )

    timeout = httpx.Timeout(30.0, read=120.0)
    try:
        with (
            httpx.Client(follow_redirects=True, timeout=timeout) as client,
            client.stream("GET", source.url, headers=headers) as response,
        ):
            if response.status_code == 416 and offset:
                if source.size and offset == source.size:
                    part_path.replace(output_path)
                    console.print(f"[green]Already downloaded:[/green] {output_path}")
                    return output_path
                part_path.unlink()
                raise RuntimeError(
                    "Server rejected the resume request; retry the download."
                )

            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "text/html" in content_type.lower():
                raise RuntimeError("CDN returned HTML instead of a video file.")

            if offset and response.status_code == 200:
                offset = 0

            content_length = int(response.headers.get("content-length") or 0)
            if response.status_code == 206 and content_length:
                total = offset + content_length
            else:
                total = content_length or source.size or None
            if source.size:
                total = source.size

            mode = "ab" if offset else "wb"
            with Progress(
                TextColumn("[cyan]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                transient=True,
            ) as progress:
                task = progress.add_task("Downloading...", total=total)
                if offset:
                    progress.update(task, completed=offset)
                with part_path.open(mode) as handle:
                    for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        progress.update(task, advance=len(chunk))
    except (httpx.HTTPError, OSError) as exc:
        raise RuntimeError(f"Download failed: {exc}") from exc

    if source.size:
        actual = part_path.stat().st_size
        if actual != source.size:
            raise RuntimeError(
                f"Download size mismatch: expected {source.size} bytes, got {actual}."
            )

    part_path.replace(output_path)
    console.print(f"[green]Done:[/green] {output_path}")
    return output_path
