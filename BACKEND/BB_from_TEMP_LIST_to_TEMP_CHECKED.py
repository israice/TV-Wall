#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMP_LIST_PATH = PROJECT_ROOT / "DATA" / "CHECK" / "TEMP_LIST.json"
TEMP_CHECKED_PATH = PROJECT_ROOT / "DATA" / "CHECK" / "TEMP_CHECKED.json"
BLACKLIST_PATH = PROJECT_ROOT / "DATA" / "CHECK" / "BLACKLIST.json"
WHITELIST_PATH = PROJECT_ROOT / "DATA" / "CHECK" / "WHITELIST.json"


def normalize(value) -> str:
    return str(value).strip()


def load_json_list(path: Path):
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array.")
    return data


def save_json_list(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def merge_blacklist(existing_blacklist, excluded_items):
    merged = []
    seen = set()

    for item in existing_blacklist:
        key = normalize(item)
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(item)

    added = 0
    for item in excluded_items:
        key = normalize(item)
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(item)
        added += 1

    return merged, added


def main() -> None:
    temp_list = load_json_list(TEMP_LIST_PATH)
    blacklist = load_json_list(BLACKLIST_PATH)
    whitelist = load_json_list(WHITELIST_PATH)

    excluded_set = {normalize(item) for item in blacklist}
    excluded_set.update(normalize(item) for item in whitelist)

    filtered_temp_list = [
        item for item in temp_list if normalize(item) not in excluded_set
    ]
    excluded_items = [
        item for item in temp_list if normalize(item) in excluded_set
    ]

    removed_count = len(temp_list) - len(filtered_temp_list)
    updated_blacklist, added_to_blacklist = merge_blacklist(blacklist, excluded_items)

    save_json_list(TEMP_CHECKED_PATH, filtered_temp_list)
    save_json_list(BLACKLIST_PATH, updated_blacklist)

    print(f"Temp list before: {len(temp_list)}")
    print(f"Blacklist: {len(blacklist)}")
    print(f"Whitelist: {len(whitelist)}")
    print(f"Excluded total (unique): {len(excluded_set)}")
    print(f"Removed: {removed_count}")
    print(f"Temp list after: {len(filtered_temp_list)}")
    print(f"Added to blacklist: {added_to_blacklist}")
    print(f"Blacklist after: {len(updated_blacklist)}")
    print(f"Saved blacklist: {BLACKLIST_PATH}")
    print(f"Saved: {TEMP_CHECKED_PATH}")


if __name__ == "__main__":
    main()
