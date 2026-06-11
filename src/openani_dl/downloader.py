import os
import subprocess
import sys
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

from openani_dl.models import EpisodeInfo, VideoSource

console = Console()


def _check_deps():
    try:
        subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        return "yt-dlp"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            check=True,
        )
        return "ffmpeg"
    except (subprocess.CalledProcessError, FileNotFoundError):
        console.print(
            "[red]Error: yt-dlp or ffmpeg not found.[/red]\n"
            "Install: pip install yt-dlp  or  https://ffmpeg.org/download.html"
        )
        sys.exit(1)
    return None


def download_episode(
    source: VideoSource,
    info: EpisodeInfo,
    output_dir: str = ".",
    quality: str = "best",
):
    _check_deps()

    out_dir = Path(output_dir) / _sanitize(info.anime_title)
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = f"S{info.season:02d}E{info.episode:02d} - {_sanitize(info.title or f'Episode {info.episode}')}.mp4"
    out_path = out_dir / filename

    if out_path.exists():
        console.print(f"[yellow]Already exists:[/yellow] {out_path}")
        return out_path

    console.print(f"[cyan]Downloading:[/cyan] {info.anime_title} - Episode {info.episode}")

    _download_m3u8(source.url, str(out_path), source.referer, quality)

    console.print(f"[green]Done:[/green] {out_path}")
    return out_path


def _download_m3u8(url: str, out_path: str, referer: str = "", quality: str = "best"):
    cmd = [
        "yt-dlp",
        "--no-progress",
        "--no-warnings",
        "--output", out_path,
        "--format", "b",
        "--merge-output-format", "mp4",
        "--remux-video", "mp4",
        "--retries", "10",
    ]

    if referer:
        cmd.extend(["--referer", referer])

    cmd.append(url)

    progress = Progress(
        TextColumn("[cyan]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        transient=True,
    )

    with progress:
        task = progress.add_task("[yellow]Downloading...", total=None)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                console.print(f"[red]yt-dlp error:[/red] {result.stderr.strip()}")
                raise RuntimeError(f"yt-dlp failed: {result.stderr}")
        finally:
            progress.remove_task(task)


def _sanitize(name: str) -> str:
    return "".join(c if c.isalnum() or c in " ._-()" else "_" for c in name).strip()


def try_direct_download(url: str, out_path: str, referer: str = ""):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"}
    if referer:
        headers["Referer"] = referer

    with httpx.Client(follow_redirects=True) as client:
        response = client.head(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return False

        content_type = response.headers.get("content-type", "")
        if "video" not in content_type and "octet-stream" not in content_type and "mpeg" not in content_type:
            return False

        total = int(response.headers.get("content-length", 0))
        if total < 1024:
            return False

        progress = Progress(
            TextColumn("[cyan]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        )

        with progress:
            task = progress.add_task("[yellow]Downloading...", total=total)
            with httpx.Client(follow_redirects=True) as dl_client:
                with dl_client.stream("GET", url, headers=headers, timeout=300) as r:
                    r.raise_for_status()
                    with open(out_path, "wb") as f:
                        for chunk in r.iter_bytes(chunk_size=8192):
                            f.write(chunk)
                            progress.update(task, advance=len(chunk))

        console.print(f"[green]Done:[/green] {out_path}")
        return True
