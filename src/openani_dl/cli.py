from __future__ import annotations

import asyncio
import re
import sys

import click
from rich.console import Console
from rich.panel import Panel

from openani_dl.client import OpenAnimeClient
from openani_dl.downloader import download_episode
from openani_dl.models import EpisodeInfo

console = Console()

URL_RE = re.compile(
    r"^https?://(?:www\.)?openani\.me/anime/([^/]+)/(\d+)/(\d+)"
)


def parse_url(url: str) -> tuple[str, int, int] | None:
    match = URL_RE.match(url)
    if not match:
        return None
    return match.group(1), int(match.group(2)), int(match.group(3))


@click.group()
def main():
    """openani.me anime downloader"""


def _download_source(
    source_url: str,
    referer: str,
    info: EpisodeInfo,
    output: str,
    quality: str,
):
    from openani_dl.downloader import download_episode
    from openani_dl.models import VideoSource

    source = VideoSource(url=source_url, referer=referer)
    download_episode(source, info, output, quality)


@main.command()
@click.argument("url")
@click.option("-o", "--output", default=".", help="Output directory")
@click.option("-q", "--quality", default="best", help="Video quality (best, 1080, 720, 480)")
@click.option(
    "--browser/--no-browser",
    default=False,
    help="Use Playwright browser (for Cloudflare)",
)
def download(url: str, output: str, quality: str, browser: bool):
    """Download episode from URL"""
    parsed = parse_url(url)
    if not parsed:
        console.print("[red]Invalid URL. Example: https://openani.me/anime/slug/1/1[/red]")
        sys.exit(1)

    slug, season, episode = parsed
    info = EpisodeInfo(
        slug=slug,
        season=season,
        episode=episode,
        title=f"Episode {episode}",
        anime_title=slug.replace("-", " ").title(),
    )

    console.print(Panel(f"[bold]openani-dl[/bold]\n{url}", width=60))

    if browser:
        return _download_with_browser(slug, season, episode, info, output, quality)

    client = OpenAnimeClient()

    with console.status("[cyan]Loading page..."):
        html = client.fetch_anime_page(slug, season, episode)

    console.print("[dim]Scanning embedded data...[/dim]")
    source = client.extract_from_page_data(html, slug=slug, season=str(season), quality=quality)

    if source:
        console.print(f"[green]Video source:[/green] {source.url[:100]}...")
        download_episode(source, info, output, quality)
        return

    console.print("[yellow]Direct video URL not found, querying API...[/yellow]")
    with console.status("[cyan]API..."):
        anisub = client.get_anisub(slug)

    if anisub:
        console.print(f"[green]API responded ({len(anisub)} sources)[/green]")
        console.print("[yellow]Could not resolve video URL from these sources.[/yellow]")
        console.print("[yellow]For detailed inspection use --browser:[/yellow]")
        console.print(f"  openani-dl download --browser \"{url}\"")
    else:
        console.print("[red]Video source not found.[/red]")
        console.print("[yellow]Solutions:")
        console.print("  1. Try with Playwright: pip install 'openani-dl[playwright]'; playwright install chromium")
        console.print(f"  2. openani-dl download --browser \"{url}\"")
        console.print("[/yellow]")
        sys.exit(1)


def _download_with_browser(slug, season, episode, info, output, quality):
    try:
        from openani_dl.playwright_scraper import find_source_async
    except ImportError:
        console.print("[red]Playwright required: pip install 'openani-dl[playwright]' && playwright install chromium[/red]")
        sys.exit(1)

    console.print("[cyan]Opening browser with Playwright...[/cyan]")

    source = asyncio.run(find_source_async(slug, season, episode))

    if source:
        console.print(f"[green]Video source found:[/green] {source.url[:100]}...")
        download_episode(source, info, output, quality)
    else:
        console.print("[red]Could not find video source even with browser.[/red]")
        sys.exit(1)


@main.command()
@click.argument("url")
@click.option("-s", "--start", type=int, default=1, help="Start episode")
@click.option("-e", "--end", type=int, required=True, help="End episode")
@click.option("-o", "--output", default=".", help="Output directory")
@click.option("-q", "--quality", default="best", help="Video quality")
@click.option("--browser/--no-browser", default=False, help="Use Playwright browser")
def batch(url: str, start: int, end: int, output: str, quality: str, browser: bool):
    """Download a range of episodes"""
    parsed = parse_url(url)
    if not parsed:
        console.print("[red]Invalid URL[/red]")
        sys.exit(1)

    slug, season, _ = parsed
    console.print(Panel(f"[bold]Batch download:[/bold] {slug} S{season} Episodes {start}-{end}", width=60))

    for ep in range(start, end + 1):
        info = EpisodeInfo(
            slug=slug,
            season=season,
            episode=ep,
            title=f"Episode {ep}",
            anime_title=slug.replace("-", " ").title(),
        )

        if browser:
            _download_with_browser(slug, season, ep, info, output, quality)
        else:
            client = OpenAnimeClient()
            with console.status(f"[cyan]Loading episode {ep}..."):
                html = client.fetch_anime_page(slug, season, ep)

            source = client.extract_from_page_data(html, slug=slug, season=str(season), quality=quality)

            if source:
                download_episode(source, info, output, quality)
            else:
                console.print(f"[yellow]No source found for episode {ep}, skipping...[/yellow]")

    console.print("[green]Batch download complete![/green]")


@main.command()
@click.argument("url")
def inspect(url: str):
    """Show page info and available video sources"""
    parsed = parse_url(url)
    if not parsed:
        console.print("[red]Invalid URL[/red]")
        sys.exit(1)

    slug, season, episode = parsed
    client = OpenAnimeClient()
    from openani_dl.scraper import extract_video_files, parse_page, extract_anime_data

    with console.status("[cyan]Loading page..."):
        html = client.fetch_anime_page(slug, season, episode)

    page = parse_page(html)
    anime = extract_anime_data(html)

    console.print("[bold]Page Info:[/bold]")
    console.print(f"  Slug: {slug}")
    console.print(f"  Season: {season}")
    console.print(f"  Episode: {episode}")
    console.print(f"  CDN Host: {page.random_cdn_host or 'Not found'}")
    console.print(f"  Token: {'Yes' if page.token else 'No'}")

    files = extract_video_files(html, slug=slug, season=str(season))
    if files:
        console.print(f"\n[bold]Video files ({len(files)} found):[/bold]")
        for f in files:
            console.print(f"  {f['resolution']}p: {f['url']}")

    console.print("\n[bold]API Responses:[/bold]")
    for endpoint in [f"/anime/{slug}", f"/anime/{slug}/anisub"]:
        with console.status(f"[cyan]{endpoint}..."):
            result = client.api_get(endpoint)
        if result:
            display = str(result)
            if len(display) > 300:
                display = display[:300] + "..."
            console.print(f"  [green]200[/green] {endpoint}")
            console.print(f"    {display}")
        else:
            console.print(f"  [yellow]401/404/None[/yellow] {endpoint}")

    client.close()


@main.command()
def version():
    """Show version info"""
    from openani_dl import __version__
    console.print(f"openani-dl v{__version__}")


if __name__ == "__main__":
    main()
