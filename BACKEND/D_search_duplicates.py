#!/usr/bin/env python3
"""
Check all JSON list files for duplicate URLs.

Reports:
  1. Duplicates WITHIN a single file
  2. Duplicates BETWEEN different files
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LISTS_DIR = PROJECT_ROOT / "DATA" / "LISTS"

# Priority order: first = highest priority (keep URL here).
# When a URL exists in multiple files, it is removed from the lower-priority ones.
FILES_BY_PRIORITY = [
    LISTS_DIR / "BLACKLIST.json",
    LISTS_DIR / "NEWS.json",
    LISTS_DIR / "NEWS2.json",
    LISTS_DIR / "SPORT.json",
    LISTS_DIR / "MUSIC.json",
    LISTS_DIR / "NEWS3.json",
    LISTS_DIR / "ALL.json",
]


def load_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        print(f"  WARNING: {path.name} is not valid JSON, skipping")
        return []
    if not isinstance(data, list):
        print(f"  WARNING: {path.name} root is not a list, skipping")
        return []
    return data


def dedup_within(name: str, urls: list[str]) -> tuple[int, list[str]]:
    """Remove duplicates within a file, keeping first occurrence. Return (count, cleaned list)."""
    seen: set[str] = set()
    cleaned: list[str] = []
    duplicates = 0
    for i, url in enumerate(urls):
        if url in seen:
            duplicates += 1
            print(f"  {name}: duplicate at line {i + 1}: \"{url}\"")
        else:
            seen.add(url)
            cleaned.append(url)
    return duplicates, cleaned


def check_duplicates_between(
    file_data: dict[str, list[str]],
    priority: list[str],
) -> tuple[int, dict[str, set[str]]]:
    """Return (duplicate_count, {filename: set of urls to remove})."""
    url_to_files: dict[str, list[str]] = defaultdict(list)
    for name, urls in file_data.items():
        for url in set(urls):
            url_to_files[url].append(name)

    name_to_rank = {name: i for i, name in enumerate(priority)}
    duplicates = 0
    removals: dict[str, set[str]] = defaultdict(set)

    for url, files in sorted(url_to_files.items()):
        if len(files) <= 1:
            continue
        print(f"  \"{url}\" — found in: {', '.join(files)}")
        duplicates += 1
        # Keep in highest-priority file, remove from the rest
        ranked = sorted(files, key=lambda f: name_to_rank.get(f, 999))
        for loser in ranked[1:]:
            removals[loser].add(url)

    return duplicates, removals


def main() -> None:
    file_data: dict[str, list[str]] = {}

    priority_names = [p.name for p in FILES_BY_PRIORITY]

    print("=" * 60)
    print("Loading files...")
    print("=" * 60)
    for path in FILES_BY_PRIORITY:
        urls = load_list(path)
        file_data[path.name] = urls
        print(f"  {path.name}: {len(urls)} URLs")

    total_issues = 0

    print()
    print("=" * 60)
    print("1. Duplicates WITHIN each file")
    print("=" * 60)
    within_total = 0
    for name, urls in file_data.items():
        count, cleaned = dedup_within(name, urls)
        if count > 0:
            within_total += count
            file_data[name] = cleaned
            path = LISTS_DIR / name
            path.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  {name}: {len(urls)} -> {len(cleaned)} ({count} removed)")
    if within_total == 0:
        print("  No duplicates found.")
    else:
        print(f"  Total: {within_total} duplicate(s) removed")
    total_issues += within_total

    print()
    print("=" * 60)
    print("2. Duplicates BETWEEN files")
    print("=" * 60)
    between_total, removals = check_duplicates_between(file_data, priority_names)
    if between_total == 0:
        print("  No cross-file duplicates found.")
    else:
        print(f"  Total: {between_total} URL(s) in multiple files")
    total_issues += between_total

    files_with_removals = {k: v for k, v in removals.items() if v}
    if files_with_removals:
        print()
        print("=" * 60)
        print("3. Removing duplicates (keeping in higher-priority file)")
        print("=" * 60)
        for name in priority_names:
            if name not in files_with_removals:
                continue
            urls_to_remove = files_with_removals[name]
            path = LISTS_DIR / name
            before = len(file_data[name])
            cleaned = [u for u in file_data[name] if u not in urls_to_remove]
            path.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  {name}: {before} -> {len(cleaned)} ({before - len(cleaned)} removed)")

    print()
    print("=" * 60)
    if total_issues == 0:
        print("All clean — no duplicates found.")
    else:
        print(f"Found {total_issues} issue(s) total.")
    print("=" * 60)

    sys.exit(1 if total_issues else 0)


if __name__ == "__main__":
    main()
