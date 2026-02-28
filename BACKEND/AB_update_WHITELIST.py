#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WHITELIST_PATH = PROJECT_ROOT / "DATA" / "CHECK" / "WHITELIST.json"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import SETTINGS as settings


class SourceJob:
    def __init__(self, input_path: Path, output_path: Path) -> None:
        self.input_path = input_path
        self.output_path = output_path


def _path_from_setting(value: Any) -> Path:
    return Path(value).expanduser().resolve()


def _normalize_source_jobs(raw: Any) -> list[SourceJob]:
    jobs: list[SourceJob] = []
    if not isinstance(raw, list):
        return jobs
    for item in raw:
        if isinstance(item, str) and item.strip():
            input_path = _path_from_setting(item.strip())
            jobs.append(SourceJob(input_path=input_path, output_path=input_path))
            continue
        if isinstance(item, dict):
            input_value = item.get("input")
            if not isinstance(input_value, str) or not input_value.strip():
                continue
            output_value = item.get("output")
            input_path = _path_from_setting(input_value.strip())
            if isinstance(output_value, str) and output_value.strip():
                output_path = _path_from_setting(output_value.strip())
            else:
                output_path = input_path
            jobs.append(SourceJob(input_path=input_path, output_path=output_path))
    return jobs


def get_source_jobs() -> list[SourceJob]:
    configured = _normalize_source_jobs(getattr(settings, "CHECK_M3U8_SOURCE_JSON_FILES", None))
    if configured:
        return configured

    input_path = _path_from_setting(settings.CHECK_M3U8_JSON_FILE)
    output_value = getattr(settings, "CHECK_M3U8_OUTPUT_JSON_FILE", None)
    output_path = _path_from_setting(output_value) if output_value else input_path
    return [SourceJob(input_path=input_path, output_path=output_path)]


def load_urls_from_json(path: Path) -> list[str]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array in {path}")
    urls: list[str] = []
    for item in data:
        if not isinstance(item, str):
            continue
        url = item.strip()
        if url:
            urls.append(url)
    return urls


def save_urls_to_json(path: Path, urls: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(urls, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> None:
    source_jobs = get_source_jobs()
    merged_urls: list[str] = []
    seen: set[str] = set()
    total_seen_in_sources = 0
    processed_files = 0

    print(f"Source files to read: {len(source_jobs)}")
    for idx, job in enumerate(source_jobs, start=1):
        path = job.input_path
        print(f"[{idx}/{len(source_jobs)}] {path}")
        if not path.exists():
            print("SKIP: input file not found.")
            continue
        try:
            urls = load_urls_from_json(path)
        except Exception as exc:
            print(f"SKIP: failed to read input JSON ({exc})")
            continue

        processed_files += 1
        total_seen_in_sources += len(urls)
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            merged_urls.append(url)

    save_urls_to_json(WHITELIST_PATH, merged_urls)

    print("\n=== Summary ===")
    print(f"Processed source files: {processed_files}/{len(source_jobs)}")
    print(f"URLs found in sources: {total_seen_in_sources}")
    print(f"Unique URLs saved: {len(merged_urls)}")
    print(f"Saved: {WHITELIST_PATH}")


if __name__ == "__main__":
    main()
