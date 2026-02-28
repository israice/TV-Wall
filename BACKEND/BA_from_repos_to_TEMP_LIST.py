#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import sys
from pathlib import Path
from urllib import error, parse, request

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import SETTINGS as settings

OUTPUT_JSON_FILE = Path("DATA/CHECK/TEMP_LIST.json").resolve()
DEFAULT_LINK_PATTERN = r'https?://[^\s)"]+?\.m3u8(?:\?[^\s)"]*)?'
DEFAULT_TIMEOUT = 20
MD_ACTIVE_LINK_PATTERN = re.compile(r"\[\>\]\((https?://[^)]+)\)")


def is_direct_playlist_url(source):
    value = (source or "").strip().lower()
    return value.startswith(("http://", "https://")) and (
        ".m3u" in value or ".m3u8" in value
    )


def parse_github_repo(repo_url):
    """Convert GitHub URL into (owner, repo) pair."""
    url = (repo_url or "").strip()
    if not url:
        raise ValueError("Empty repository URL")

    parsed = parse.urlparse(url)
    if parsed.netloc.lower() != "github.com":
        raise ValueError(f"Unsupported host in URL: {repo_url}")

    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]

    parts = [part for part in path.split("/") if part]
    if len(parts) < 2:
        raise ValueError(f"Invalid repository URL: {repo_url}")

    owner, repo = parts[0], parts[1]
    return owner, repo


def fetch_json(url, timeout):
    req = request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": settings.GET_MD_LIST_USER_AGENT,
        },
    )
    with request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url, timeout):
    req = request.Request(
        url,
        headers={"User-Agent": settings.GET_M3U8_USER_AGENT},
    )
    with request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def get_timeout():
    value = getattr(settings, "GET_M3U8_TIMEOUT_SECONDS", DEFAULT_TIMEOUT)
    return value if isinstance(value, (int, float)) and value > 0 else DEFAULT_TIMEOUT


def get_repo_default_branch(owner, repo):
    meta_url = f"https://api.github.com/repos/{owner}/{repo}"
    payload = fetch_json(meta_url, get_timeout())
    return payload.get("default_branch", "master")


def extract_m3u8_links_from_text(text):
    pattern = getattr(settings, "GET_M3U8_LINK_PATTERN", DEFAULT_LINK_PATTERN)
    links = re.findall(pattern, text)
    return [link for link in links if ".m3u8" in link.lower()]


def dedupe_keep_order(links):
    seen = set()
    result = []
    for link in links:
        normalized = link.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def collect_from_playlist_file(owner, repo, branch):
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/playlist.m3u8"
    text = fetch_text(raw_url, get_timeout())
    links = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith(("http://", "https://")) and ".m3u8" in line.lower():
            links.append(line)
    return dedupe_keep_order(links)


def collect_from_lists_md(owner, repo):
    lists_api = f"https://api.github.com/repos/{owner}/{repo}/contents/lists"
    items = fetch_json(lists_api, get_timeout())
    md_items = [
        item for item in items
        if item.get("type") == "file" and str(item.get("name", "")).lower().endswith(".md")
    ]

    links = []
    for item in md_items:
        download_url = item.get("download_url")
        if not download_url:
            continue
        try:
            text = fetch_text(download_url, get_timeout())
        except (error.URLError, TimeoutError, ValueError):
            continue

        for match in MD_ACTIVE_LINK_PATTERN.findall(text):
            if ".m3u8" in match.lower():
                links.append(match.strip())
    return dedupe_keep_order(links)


def collect_from_direct_playlist_url(playlist_url):
    text = fetch_text(playlist_url, get_timeout())
    links = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith(("http://", "https://")) and ".m3u8" in line.lower():
            links.append(line)
    return dedupe_keep_order(links)


def collect_links_from_repo(repo_url):
    owner, repo = parse_github_repo(repo_url)
    branch = get_repo_default_branch(owner, repo)

    try:
        # For Free-TV/IPTV this is the canonical generated source of included channels.
        return collect_from_playlist_file(owner, repo, branch), "playlist.m3u8"
    except Exception:
        pass

    try:
        # Fallback to source markdown with only active `[>]` entries.
        return collect_from_lists_md(owner, repo), "lists/*.md [>]"
    except Exception:
        pass

    # Last fallback: shallow scan of README text only.
    readme_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"
    text = fetch_text(readme_url, get_timeout())
    return dedupe_keep_order(extract_m3u8_links_from_text(text)), "README.md"


def collect_links_from_source(source):
    if is_direct_playlist_url(source):
        return collect_from_direct_playlist_url(source), "direct .m3u/.m3u8 url"
    return collect_links_from_repo(source)


def write_links(output_file, links):
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(links, f, ensure_ascii=False, indent=2)


def main():
    source_items = getattr(settings, "M3U8_REPOS_SOURCE_LIST", [])
    if not isinstance(source_items, list) or not source_items:
        print("M3U8_REPOS_SOURCE_LIST is empty or invalid.")
        write_links(OUTPUT_JSON_FILE, [])
        return

    all_links = []
    global_seen = set()

    for source in source_items:
        print(f"Scanning source: {source}")
        try:
            repo_links, source_name = collect_links_from_source(source)
        except Exception as exc:
            print(f"  Failed: {exc}")
            continue

        new_count = 0
        for link in repo_links:
            if link not in global_seen:
                global_seen.add(link)
                all_links.append(link)
                new_count += 1
        print(f"  Source: {source_name}")
        print(f"  Found new links: {new_count}")

    write_links(OUTPUT_JSON_FILE, all_links)
    print(f"Done. Saved {len(all_links)} link(s) to: {OUTPUT_JSON_FILE}")


if __name__ == "__main__":
    main()
