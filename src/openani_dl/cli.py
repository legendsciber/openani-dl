from __future__ import annotations

import re

import click
from rich.console import Console
from rich.table import Table

from openani_dl.client import OpenAnimeClient, OpenAnimeError
from openani_dl.downloader import download_episode
from openani_dl.scraper import extract_fansubs

console = Console()

URL_RE = re.compile(
    r"^https?://(?:www\.)?openani\.me/anime/([^/]+)/(\d+)/(\d+)(?:[/?#].*)?$"
)


def parse_url(url: str) -> tuple[str, int, int] | None:
    match = URL_RE.match(url)
    if not match:
        return None
    return match.group(1), int(match.group(2)), int(match.group(3))


def _format_size(size: int) -> str:
    if not size:
        return "?"
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GiB"


@click.group()
def main() -> None:
    """openani.me anime downloader"""


@main.command()
@click.argument("url")
@click.option("-o", "--output", default=".", help="Output directory")
@click.option(
    "-q",
    "--quality",
    default="best",
    help="Video quality: best, 2160, 1080, 720, 480",
)
@click.option(
    "-f",
    "--fansub",
    default=None,
    help="Fansub name, secure name or ID (e.g. ceviribukuculer)",
)
def download(url: str, output: str, quality: str, fansub: str | None) -> None:
    """Download one episode."""
    parsed = parse_url(url)
    if not parsed:
        raise click.ClickException(
            "Invalid URL. Example: https://openani.me/anime/slug/1/1"
        )

    slug, season, episode = parsed
    client = OpenAnimeClient()
    try:
        source = client.resolve(
            slug,
            season,
            episode,
            quality=quality,
            fansub=fansub,
        )
        console.print(
            f"[bold]{source.anime_title}[/bold] "
            f"S{source.season:02d}E{source.episode:02d} - {source.episode_title}"
        )
        console.print(
            f"Fansub: [green]{source.fansub.name}[/green] | "
            f"Quality: [green]{source.resolution}p[/green] | "
            f"Size: {_format_size(source.size)}"
        )
        download_episode(source, output)
    except (OpenAnimeError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc
    finally:
        client.close()


@main.command()
@click.argument("url")
@click.option("-s", "--start", type=int, default=1, help="First episode")
@click.option("-e", "--end", type=int, required=True, help="Last episode")
@click.option("-o", "--output", default=".", help="Output directory")
@click.option(
    "-q",
    "--quality",
    default="best",
    help="Video quality: best, 2160, 1080, 720, 480",
)
@click.option(
    "-f",
    "--fansub",
    default=None,
    help="Fansub name, secure name or ID (e.g. ceviribukuculer)",
)
def batch(
    url: str,
    start: int,
    end: int,
    output: str,
    quality: str,
    fansub: str | None,
) -> None:
    """Download a range of episodes."""
    parsed = parse_url(url)
    if not parsed:
        raise click.ClickException(
            "Invalid URL. Example: https://openani.me/anime/slug/1/1"
        )
    if start < 1 or end < start:
        raise click.ClickException("Invalid episode range.")

    slug, season, _ = parsed
    console.print(
        f"[bold]Batch download:[/bold] {slug} S{season:02d} episodes {start}-{end}"
    )

    client = OpenAnimeClient()
    downloaded = 0
    failed = 0
    try:
        for episode in range(start, end + 1):
            try:
                source = client.resolve(
                    slug,
                    season,
                    episode,
                    quality=quality,
                    fansub=fansub,
                )
                console.print(
                    f"\n[bold]Episode {episode}[/bold] | "
                    f"{source.fansub.name} | {source.resolution}p"
                )
                download_episode(source, output)
                downloaded += 1
            except (OpenAnimeError, RuntimeError) as exc:
                failed += 1
                console.print(f"[red]Episode {episode} failed:[/red] {exc}")
    finally:
        client.close()

    console.print(f"\n[bold]Finished:[/bold] {downloaded} downloaded, {failed} failed.")
    if downloaded == 0:
        raise click.ClickException("No episodes were downloaded.")


@main.command()
@click.argument("url")
@click.option(
    "-f",
    "--fansub",
    default=None,
    help="Fansub name, secure name or ID (e.g. ceviribukuculer)",
)
def inspect(url: str, fansub: str | None) -> None:
    """Show fansubs and available video files."""
    parsed = parse_url(url)
    if not parsed:
        raise click.ClickException(
            "Invalid URL. Example: https://openani.me/anime/slug/1/1"
        )

    slug, season, episode = parsed
    client = OpenAnimeClient()
    try:
        html = client.fetch_page(slug, season, episode)
        fansubs = extract_fansubs(html)

        if fansubs:
            table = Table(title="Fansubs")
            table.add_column("Name")
            table.add_column("Secure name")
            table.add_column("4K")
            table.add_column("ID")
            for item in fansubs:
                table.add_row(
                    item.name,
                    item.secure_name,
                    "yes" if item.is_4k else "",
                    item.id,
                )
            console.print(table)

        data = client.get_episode_data(
            slug,
            season,
            episode,
            fansub=fansub,
            html=html,
        )
        console.print(
            f"\n[bold]{data.anime_title}[/bold] "
            f"S{data.season:02d}E{data.episode:02d} - {data.episode_title}"
        )
        console.print(f"Fansub: [green]{data.fansub.name}[/green]")

        table = Table(title="Video files")
        table.add_column("Quality")
        table.add_column("Size", justify="right")
        table.add_column("URL")
        for item in sorted(data.files, key=lambda file: file.resolution):
            table.add_row(
                f"{item.resolution}p",
                _format_size(item.size),
                item.url,
            )
        console.print(table)
    except OpenAnimeError as exc:
        raise click.ClickException(str(exc)) from exc
    finally:
        client.close()


@main.command()
def version() -> None:
    """Show version info."""
    from openani_dl import __version__

    console.print(f"openani-dl v{__version__}")


if __name__ == "__main__":
    main()
