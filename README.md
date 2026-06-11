# openani-dl

CLI tool to download videos from [openani.me](https://openani.me).

## Install

```bash
pip install openani-dl
```

For browser-based fallback (Cloudflare bypass):

```bash
pip install 'openani-dl[playwright]'
playwright install chromium
```

## Usage

**Download a single episode:**

```bash
openani-dl download "https://openani.me/anime/<slug>/<season>/<episode>" --quality 720p
```

**Batch download episodes 1-12:**

```bash
openani-dl batch "https://openani.me/anime/<slug>/<season>/1" --start 1 --end 12
```

**Inspect available video sources:**

```bash
openani-dl inspect "https://openani.me/anime/<slug>/<season>/<episode>"
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `-o, --output` | `.` | Output directory |
| `-q, --quality` | `best` | Video quality (`best`, `1080`, `720`, `480`) |
| `--browser` | `false` | Use Playwright browser for Cloudflare bypass |

## How it works

1. Fetches the episode page and extracts the CDN host and video file list from embedded JavaScript data
2. Constructs direct MP4 download URLs (no HLS/DASH)
3. Downloads using yt-dlp (supports resume, concurrent fragments)

Video files are served as plain MP4 from dynamic CDN hosts. No authentication required for video access.

## Requirements

- Python 3.10+
- yt-dlp (automatically installed)
- ffmpeg (optional, for some merge operations)
