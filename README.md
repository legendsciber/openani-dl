# openani-dl

CLI tool to download videos from [openani.me](https://openani.me).

## Install

```bash
pip install .
```

## Usage

**Download a single episode:**

```bash
openani-dl download "https://openani.me/anime/chainsaw-man/1/1" \
  --fansub ceviribukuculer --quality 2160p
```

**Download a range of episodes:**

```bash
openani-dl batch "https://openani.me/anime/chainsaw-man/1/1" \
  --start 1 --end 12 --fansub ceviribukuculer --quality 2160p
```

**Inspect fansubs and available files:**

```bash
openani-dl inspect "https://openani.me/anime/chainsaw-man/1/1"
openani-dl inspect "https://openani.me/anime/chainsaw-man/1/1" --fansub ceviribukuculer
```

### Options

| Flag | Default | Description |
| --- | --- | --- |
| `-o, --output` | `.` | Output directory |
| `-q, --quality` | `best` | `best` or a resolution such as `2160`, `1080`, `720` |
| `-f, --fansub` | page default | Fansub name, secure name or ID |

The fansub value is case- and diacritic-insensitive, so `Ceviri Bukuculer`,
`Çeviri Bükücüler` and `ceviribukuculer` all select the same fansub.

## How it works

1. Fetches the episode page to find the CDN host and the fansub list.
2. Requests the episode data from the API with the selected fansub.
3. Builds the direct MP4 URL from the CDN and downloads it with resume support.

Video files are served as plain MP4 from dynamic CDN hosts. No authentication is
required for video access.

## Requirements

- Python 3.10+
