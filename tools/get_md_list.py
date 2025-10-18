#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import csv
import requests

# GitHub API endpoint for contents of the 'lists' directory
API_URL = 'https://api.github.com/repos/Free-TV/IPTV/contents/lists'
# CSV file name in the same directory
CSV_FILE = 'tools/get_md_list.csv'
# CSV header
CSV_HEADER = ['MD_URL']

def fetch_directory_listing(api_url):
    """Fetch JSON listing of files in the GitHub 'lists' directory."""
    response = requests.get(api_url)
    response.raise_for_status()
    return response.json()

def extract_md_urls(file_list):
    """
    From the JSON list, select items of type 'file' with '.md' extension,
    and return their HTML URLs (e.g., https://github.com/.../albania.md).
    """
    md_urls = []
    for item in file_list:
        if item.get('type') == 'file' and item.get('name', '').lower().endswith('.md'):
            url = item.get('html_url')
            if url:
                md_urls.append(url)
    return md_urls

def read_existing_urls(csv_file):
    """Read existing URLs from CSV, return as a set."""
    if not os.path.isfile(csv_file):
        return set()
    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        return {row[0] for row in reader if row}

def append_new_urls(csv_file, urls):
    """Append new URLs to CSV file, adding header if file is new."""
    file_exists = os.path.isfile(csv_file)
    with open(csv_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(CSV_HEADER)
        for url in urls:
            writer.writerow([url])

def main():
    # 1. Get directory listing via API
    file_list = fetch_directory_listing(API_URL)
    # 2. Extract .md URLs
    md_urls = extract_md_urls(file_list)

    # 3. Load already saved URLs
    existing = read_existing_urls(CSV_FILE)
    # 4. Filter only new ones
    new_urls = [u for u in md_urls if u not in existing]

    # 5. Append new URLs or report none found
    if not new_urls:
        print("No new .md links found.")
    else:
        append_new_urls(CSV_FILE, new_urls)
        print(f"Added {len(new_urls)} new link(s) to {CSV_FILE}:")
        for u in new_urls:
            print(u)

if __name__ == '__main__':
    main()
