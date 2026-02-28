import asyncio
import json
from pathlib import Path
import re
from urllib.parse import quote, urljoin, urlparse

import httpx
import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles

import SETTINGS as settings

PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "FRONTEND"
DATA_DIR = PROJECT_ROOT / "DATA"
INDEX_FILE = FRONTEND_DIR / "index.html"
FAVICON_FILE = FRONTEND_DIR / "favicon.svg"
ATTR_URI_RE = re.compile(r'URI="([^"]+)"')
INDEX_STREAMS_COUNT_PLACEHOLDER = "__FRONTEND_STREAMS_COUNT__"
INDEX_STREAMS_SOURCE_URL_PLACEHOLDER = "__FRONTEND_STREAMS_SOURCE_URL__"
INDEX_PROMO_DISPLAY_SECONDS_PLACEHOLDER = "__FRONTEND_PROMO_DISPLAY_SECONDS__"
INDEX_SNAP_SCROLL_SECONDS_PLACEHOLDER = "__FRONTEND_SNAP_SCROLL_SECONDS__"
INDEX_DEV_MODE_PLACEHOLDER = "__FRONTEND_DEV_MODE__"


def validate_settings_or_raise() -> None:
    required_constants = {
        "APP_TITLE": str,
        "APP_HOST": str,
        "APP_PORT": int,
        "APP_RELOAD": bool,
        "FRONTEND_STREAMS_COUNT": int,
        "FRONTEND_STREAMS_SOURCE_URL": str,
        "FRONTEND_PROMO_DISPLAY_SECONDS": int,
        "FRONTEND_SNAP_SCROLL_SECONDS": (int, float),
        "APP_SHUTDOWN_TIMEOUT_SECONDS": int,
        "PROXY_UPSTREAM_TIMEOUT_SECONDS": int,
        "PROXY_CACHE_CONTROL": str,
        "ALLOWED_SCHEMES": tuple,
        "DEFAULT_USER_AGENT": str,
        "DEFAULT_ACCEPT_HEADER": str,
        "GET_MD_LIST_API_URL": str,
        "GET_MD_LIST_JSON_FILE": Path,
        "GET_MD_LIST_ACCEPT_HEADER": str,
        "GET_MD_LIST_USER_AGENT": str,
        "GET_MD_LIST_TIMEOUT_SECONDS": int,
        "GET_M3U8_MD_LIST_JSON": Path,
        "GET_M3U8_JSON_FILE": Path,
        "GET_M3U8_USER_AGENT": str,
        "GET_M3U8_TIMEOUT_SECONDS": int,
        "GET_M3U8_LINK_PATTERN": str,
        "GET_M3U8_DELAY_SECONDS": int,
        "CHECK_M3U8_JSON_FILE": Path,
        "CHECK_M3U8_DELAY_SECONDS": int,
        "CHECK_M3U8_TIMEOUT_SECONDS": int,
    }

    missing = []
    empty = []
    invalid_type = []

    for name, expected_type in required_constants.items():
        if not hasattr(settings, name):
            missing.append(name)
            continue

        value = getattr(settings, name)
        if value is None or (isinstance(value, str) and not value.strip()):
            empty.append(name)
            continue

        if not isinstance(value, expected_type):
            type_name = (
                expected_type.__name__
                if isinstance(expected_type, type)
                else "/".join(t.__name__ for t in expected_type)
            )
            invalid_type.append(
                f"{name}: expected {type_name}, got {type(value).__name__}"
            )

    if missing or empty or invalid_type:
        errors = []
        if missing:
            errors.append("Missing constants: " + ", ".join(sorted(missing)))
        if empty:
            errors.append("Empty constants: " + ", ".join(sorted(empty)))
        if invalid_type:
            errors.append("Invalid types: " + "; ".join(invalid_type))
        raise RuntimeError("SETTINGS.py validation failed. " + " | ".join(errors))


validate_settings_or_raise()

app = FastAPI(title=settings.APP_TITLE)

# Static assets: JSON and promo GIF files.
app.mount("/DATA", StaticFiles(directory=DATA_DIR), name="data")


@app.get("/", include_in_schema=False)
def serve_index() -> HTMLResponse:
    html = INDEX_FILE.read_text(encoding="utf-8")
    html = html.replace(
        INDEX_STREAMS_COUNT_PLACEHOLDER, str(max(0, settings.FRONTEND_STREAMS_COUNT))
    )
    html = html.replace(
        INDEX_STREAMS_SOURCE_URL_PLACEHOLDER, settings.FRONTEND_STREAMS_SOURCE_URL
    )
    html = html.replace(
        INDEX_PROMO_DISPLAY_SECONDS_PLACEHOLDER,
        str(max(0, settings.FRONTEND_PROMO_DISPLAY_SECONDS)),
    )
    html = html.replace(
        INDEX_SNAP_SCROLL_SECONDS_PLACEHOLDER,
        str(max(0, settings.FRONTEND_SNAP_SCROLL_SECONDS)),
    )
    html = html.replace(
        INDEX_DEV_MODE_PLACEHOLDER,
        "true" if settings.DEV_MODE else "false",
    )
    return HTMLResponse(content=html)


ALLOWED_LISTS = {
    "music": DATA_DIR / "LISTS" / "MUSIC.json",
    "news": DATA_DIR / "LISTS" / "NEWS.json",
    "sport": DATA_DIR / "LISTS" / "SPORT.json",
    "all": DATA_DIR / "LISTS" / "ALL.json",
    "blacklist": DATA_DIR / "LISTS" / "BLACKLIST.json",
}


URL_TO_LIST_KEY = {v.stem.upper(): k for k, v in ALLOWED_LISTS.items()}


class SendToListRequest(BaseModel):
    url: str
    target: str
    source: str = ""


def _resolve_source_key(source_url: str) -> str | None:
    for key, path in ALLOWED_LISTS.items():
        if key in source_url.lower() or path.stem.upper() in source_url.upper():
            return key
    return None


@app.post("/api/send-to-list", include_in_schema=False)
def send_to_list(body: SendToListRequest) -> JSONResponse:
    if not settings.DEV_MODE:
        return JSONResponse({"error": "dev mode only"}, status_code=403)

    target_path = ALLOWED_LISTS.get(body.target)
    if not target_path:
        return JSONResponse({"error": f"unknown target: {body.target}"}, status_code=400)

    # Remove from source list
    source_key = _resolve_source_key(body.source)
    if source_key and source_key != body.target:
        source_path = ALLOWED_LISTS[source_key]
        if source_path.exists():
            try:
                source_items = json.loads(source_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                source_items = []
            if body.url in source_items:
                source_items.remove(body.url)
                source_path.write_text(
                    json.dumps(source_items, indent=2, ensure_ascii=False), encoding="utf-8"
                )

    # Add to target list
    items: list[str] = []
    if target_path.exists():
        try:
            items = json.loads(target_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            items = []

    if body.url in items:
        items.remove(body.url)

    items.insert(0, body.url)
    target_path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")

    return JSONResponse({"ok": True, "target": body.target, "source": source_key or ""})


@app.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
def chrome_devtools_probe() -> Response:
    return Response(status_code=204)


@app.get("/favicon.svg", include_in_schema=False)
def favicon_svg() -> FileResponse:
    return FileResponse(FAVICON_FILE, media_type="image/svg+xml")


def build_proxy_url(target_url: str) -> str:
    return f"/proxy?url={quote(target_url, safe='')}"


def rewrite_attr_uri(line: str, base_url: str) -> str:
    def repl(match: re.Match[str]) -> str:
        raw = match.group(1)
        absolute = urljoin(base_url, raw)
        return f'URI="{build_proxy_url(absolute)}"'

    return ATTR_URI_RE.sub(repl, line)


def rewrite_m3u8(m3u8_text: str, base_url: str) -> str:
    out_lines: list[str] = []
    for line in m3u8_text.splitlines():
        stripped = line.strip()
        if not stripped:
            out_lines.append(line)
            continue

        if stripped.startswith("#"):
            if "URI=" in line:
                out_lines.append(rewrite_attr_uri(line, base_url))
            else:
                out_lines.append(line)
            continue

        absolute = urljoin(base_url, stripped)
        out_lines.append(build_proxy_url(absolute))

    return "\n".join(out_lines)


@app.get("/proxy", include_in_schema=False)
async def proxy_hls(request: Request, url: str = Query(...)) -> Response:
    parsed = urlparse(url)
    if parsed.scheme not in settings.ALLOWED_SCHEMES:
        return Response(content="Unsupported URL scheme", status_code=400)

    headers = {
        "User-Agent": request.headers.get("user-agent", settings.DEFAULT_USER_AGENT),
        "Accept": request.headers.get("accept", settings.DEFAULT_ACCEPT_HEADER),
    }
    range_header = request.headers.get("range")
    if range_header:
        headers["Range"] = range_header

    try:
        timeout = httpx.Timeout(settings.PROXY_UPSTREAM_TIMEOUT_SECONDS)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            upstream = await client.get(url, headers=headers)

        body = upstream.content
        final_url = str(upstream.url)
        content_type = upstream.headers.get("Content-Type", "application/octet-stream")
        status_code = upstream.status_code

        is_m3u8 = (
            ".m3u8" in urlparse(final_url).path.lower()
            or "mpegurl" in content_type.lower()
            or body.lstrip().startswith(b"#EXTM3U")
        )

        if is_m3u8:
            text = body.decode("utf-8", errors="replace")
            rewritten = rewrite_m3u8(text, final_url)
            return Response(
                content=rewritten.encode("utf-8"),
                media_type="application/vnd.apple.mpegurl",
                status_code=status_code,
                headers={"Cache-Control": settings.PROXY_CACHE_CONTROL},
            )

        pass_headers = {}
        for key in ("Content-Range", "Accept-Ranges", "Content-Length"):
            val = upstream.headers.get(key)
            if val:
                pass_headers[key] = val
        pass_headers["Cache-Control"] = settings.PROXY_CACHE_CONTROL

        return Response(
            content=body,
            media_type=content_type.split(";")[0].strip(),
            status_code=status_code,
            headers=pass_headers,
        )
    except asyncio.CancelledError:
        # During shutdown uvicorn may cancel in-flight requests; avoid noisy traceback.
        return Response(content=b"Request cancelled during shutdown", status_code=499)
    except httpx.HTTPStatusError as exc:
        return Response(
            content=f"Upstream HTTP error: {exc.response.status_code}".encode("utf-8"),
            status_code=502,
            media_type="text/plain",
        )
    except httpx.TimeoutException:
        return Response(
            content=b"Upstream timeout",
            status_code=504,
            media_type="text/plain",
        )
    except httpx.RequestError as exc:
        return Response(
            content=f"Upstream connection error: {exc}".encode("utf-8"),
            status_code=502,
            media_type="text/plain",
        )


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> RedirectResponse:
    return RedirectResponse(url="/favicon.svg", status_code=307)


if __name__ == "__main__":
    uvicorn.run(
        "run:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=False,
        timeout_graceful_shutdown=settings.APP_SHUTDOWN_TIMEOUT_SECONDS,
    )
