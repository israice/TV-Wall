import os
from pathlib import Path


APP_TITLE = "LiveStream TV Wall"
APP_HOST = os.environ.get("APP_HOST", "127.0.0.1")
APP_PORT = int(os.environ.get("APP_PORT", 5013))
APP_RELOAD = False
DEV_MODE = os.environ.get("DEV_MODE", "1").lower() in ("1", "true")
FRONTEND_STREAMS_COUNT = 9
FRONTEND_STREAMS_SOURCE_URL = "/DATA/connected.json"
FRONTEND_PROMO_DISPLAY_SECONDS = 2
FRONTEND_SNAP_SCROLL_SECONDS = 1.5
PROXY_UPSTREAM_TIMEOUT_SECONDS = 8
APP_SHUTDOWN_TIMEOUT_SECONDS = 2
PROXY_CACHE_CONTROL = "no-store"
ALLOWED_SCHEMES = ("http", "https")
DEFAULT_USER_AGENT = "Mozilla/5.0"
DEFAULT_ACCEPT_HEADER = "*/*"
M3U8_REPOS_SOURCE_LIST = [
    "https://github.com/Free-TV/IPTV.git",
    "https://iptv-org.github.io/iptv/index.m3u",
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",
    "https://raw.githubusercontent.com/MARIKO578/IPTV/master/playlist.m3u8",
]

GET_MD_LIST_API_URL = "https://api.github.com/repos/Free-TV/IPTV/contents/lists"
GET_MD_LIST_JSON_FILE = Path("DATA/CHECK/TEMP_CHECKED.json").resolve()
GET_MD_LIST_ACCEPT_HEADER = "application/vnd.github+json"
GET_MD_LIST_USER_AGENT = "HTML-LiveStream-TV-Wall/1.0"
GET_MD_LIST_TIMEOUT_SECONDS = 20

GET_M3U8_MD_LIST_JSON = Path("DATA/CHECK/TEMP_CHECKED.json").resolve()
GET_M3U8_JSON_FILE = Path("DATA/CHECK/TEMP_LIST.json").resolve()
GET_M3U8_USER_AGENT = "HTML-LiveStream-TV-Wall/1.0"
GET_M3U8_TIMEOUT_SECONDS = 20
GET_M3U8_LINK_PATTERN = r'https://[^\s)"]+?\.m3u8'
GET_M3U8_DELAY_SECONDS = 3

CHECK_M3U8_JSON_FILE = Path("DATA/CHECK/TEMP_LIST.json").resolve()
CHECK_M3U8_OUTPUT_JSON_FILE = Path("DATA/CHECK/TEMP_CHECKED.json").resolve()
# Each string item means in-place cleanup/sort.
# Dict format allows custom output path: {"input": "...", "output": "..."}.
CHECK_M3U8_SOURCE_JSON_FILES = [
    "DATA/LISTS/NEWS.json",
    "DATA/LISTS/SPORT.json",
    "DATA/LISTS/ALL.json",
] + [str(path.as_posix()) for path in sorted(Path("DATA/WORLD").glob("*.json"))]
CHECK_M3U8_MAX_WORKERS = 80
CHECK_M3U8_DELAY_SECONDS = 1
CHECK_M3U8_TIMEOUT_SECONDS = 5
CHECK_M3U8_TIMEOUT_RETRIES = 2
CHECK_M3U8_SEGMENT_SAMPLE_COUNT = 3
CHECK_M3U8_MIN_SUCCESSFUL_SEGMENTS = 2
CHECK_M3U8_MAX_SEGMENT_DURATION = 10
