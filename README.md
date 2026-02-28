<h1 align="center">LiveStream TV Wall</h1>

<p align="center">
  HLS live-stream dashboard with category filters, snap-scroll pages and proxy playback.<br/>
  Click any tile to unmute + fullscreen; click again to exit.
</p>

<p align="center">
  <a href="https://github.com/israice/LiveStream-Wall/stargazers">
    <img alt="GitHub stars" src="https://img.shields.io/github/stars/israice/LiveStream-Wall?style=for-the-badge&logo=github" />
  </a>
  <a href="https://github.com/israice/LiveStream-Wall/forks">
    <img alt="GitHub forks" src="https://img.shields.io/github/forks/israice/LiveStream-Wall?style=for-the-badge&logo=github" />
  </a>
  <img alt="Last commit" src="https://img.shields.io/github/last-commit/israice/LiveStream-Wall?style=for-the-badge" />
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img alt="Uvicorn" src="https://img.shields.io/badge/Uvicorn-2F4F4F?style=for-the-badge&logo=gunicorn&logoColor=white" />
  <img alt="Pydantic" src="https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge&logo=pydantic&logoColor=white" />
  <img alt="HTTPX" src="https://img.shields.io/badge/HTTPX-3B3B3B?style=for-the-badge" />
  <img alt="aiohttp" src="https://img.shields.io/badge/aiohttp-2C5BB4?style=for-the-badge&logo=aiohttp&logoColor=white" />
  <img alt="hls.js" src="https://img.shields.io/badge/hls.js-E34F26?style=for-the-badge&logo=javascript&logoColor=white" />
  <img alt="Docker" src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
</p>

## Live Website

> https://tv.weforks.org/

## Preview

<p align="center">
  <img src="https://i.postimg.cc/nr8PwWmk/screenshot.png" alt="LiveStream TV Wall screenshot">
</p>

## Features

- **HLS playback** via [hls.js](https://github.com/video-dev/hls.js/) with proxy rewriting
- **Category filters** — NEWS, SPORT, MUSIC, ALL (right side panel)
- **Country filters** — left side panel with flags
- **Grid layout** — 1 / 4 / 9 / 16 slots per screen (top panel controls)
- **Snap scroll** — smooth page-by-page navigation (mouse wheel, touch, keyboard)
- **Fullscreen** — click tile to unmute + fullscreen, click again to exit
- **Promo overlays** — configurable display on fullscreen exit
- **Dev context menu** — right-click on video to move streams between lists (dev mode only)
- **Docker ready** — single-command production deployment

## Project Structure

```
FRONTEND/          Web UI (index.html + favicon.svg)
BACKEND/           Stream list management scripts
DATA/
  LISTS/           Stream playlists (NEWS, SPORT, MUSIC, ALL, BLACKLIST, WHITELIST)
  WORLD/           Country-specific stream lists
  PROMOS/          Promo overlay images
  BUTTOM_ICONS/    Support platform icons
SETTINGS.py        All configuration constants
run.py             FastAPI server with HLS proxy
Dockerfile
docker-compose.yml
```

## Quick Start

### Development

```bash
pip install -r requirements.txt
python run.py
```

Opens at `http://localhost:8000`. DEV_MODE is enabled by default — right-click context menu available.

### Production (Docker)

```bash
docker compose up -d --build
```

Runs on port 80. DEV_MODE is disabled via `docker-compose.yml`.

## Configuration

All settings are in `SETTINGS.py`:

| Setting | Default | Description |
|---|---|---|
| `APP_HOST` | `127.0.0.1` | Server bind address |
| `APP_PORT` | `8000` | Server port |
| `DEV_MODE` | `True` | Enable dev tools (context menu) |
| `FRONTEND_STREAMS_COUNT` | `9` | Streams per page |
| `FRONTEND_PROMO_DISPLAY_SECONDS` | `2` | Promo overlay duration |
| `FRONTEND_SNAP_SCROLL_SECONDS` | `1.5` | Snap scroll animation duration |
| `PROXY_UPSTREAM_TIMEOUT_SECONDS` | `8` | HLS proxy timeout |

Environment variables (`APP_HOST`, `APP_PORT`, `DEV_MODE`) override defaults.

## Stream Lists

| File | Description |
|---|---|
| `DATA/LISTS/NEWS.json` | News channels |
| `DATA/LISTS/SPORT.json` | Sport channels |
| `DATA/LISTS/MUSIC.json` | Music channels |
| `DATA/LISTS/ALL.json` | All verified channels |
| `DATA/LISTS/BLACKLIST.json` | Blocked streams |
| `DATA/LISTS/WHITELIST.json` | Protected streams |

Each file is a JSON array of m3u8 URLs.

## Backend Scripts

Run from project root:

| Script | Purpose |
|---|---|
| `BACKEND/A_run.py` | Run full pipeline |
| `BACKEND/AA_check_all_existing.py` | Validate existing lists |
| `BACKEND/AB_update_WHITELIST.py` | Update whitelist |
| `BACKEND/BA_from_repos_to_TEMP_LIST.py` | Collect m3u8 links from repos |
| `BACKEND/BB_from_TEMP_LIST_to_TEMP_CHECKED.py` | Check stream availability |
| `BACKEND/BC_from_TEMP_CHECKED_to_ALL.py` | Merge checked streams to ALL.json |
| `BACKEND/C_check_file_manualy.py` | Manual stream verification |

## License

Licensed under the MIT License.
