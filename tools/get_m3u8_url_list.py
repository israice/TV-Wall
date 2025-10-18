#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import csv
import time
import requests

# CSV file with list of Markdown URLs (one per row; non-HTTP rows are skipped)
MD_LIST_CSV = os.path.join('tools', 'get_md_list.csv')
# CSV to store extracted m3u8 URLs
CSV_FILE = os.path.join('tools', 'get_m3u8_url_list.csv')
# Header for output CSV
CSV_HEADER = ['TV_URL']

def fetch_markdown(url):
    """Fetch the raw markdown content from the given URL."""
    response = requests.get(url)
    response.raise_for_status()
    return response.text

def extract_m3u8_links(text):
    """Extract all https://...m3u8 links from the text."""
    pattern = r'https://[^\s)"]+?\.m3u8'
    return re.findall(pattern, text)

def read_existing_urls(csv_file):
    """Read existing URLs from CSV, return as a set."""
    if not os.path.isfile(csv_file):
        return set()
    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header if present
        return {row[0] for row in reader if row}

def append_new_urls(csv_file, urls):
    """Append new URLs to CSV file."""
    file_exists = os.path.isfile(csv_file)
    with open(csv_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(CSV_HEADER)
        for url in urls:
            writer.writerow([url])

def read_md_list(csv_file):
    """Read Markdown URLs from CSV; skip non-HTTP rows."""
    urls = []
    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if row and row[0].startswith('http'):
                urls.append(row[0])
    return urls

def main():
    # Load already-saved m3u8 URLs
    existing = read_existing_urls(CSV_FILE)
    # Load list of Markdown URLs
    md_urls = read_md_list(MD_LIST_CSV)

    for md_url in md_urls:
        print(f"Processing: {md_url}")
        try:
            md_text = fetch_markdown(md_url)
        except Exception as e:
            print(f"Failed to fetch {md_url}: {e}")
            continue

        all_links = extract_m3u8_links(md_text)
        new_links = [link for link in all_links if link not in existing]

        if not new_links:
            print("  No new .m3u8 links found.")
        else:
            append_new_urls(CSV_FILE, new_links)
            existing.update(new_links)

        # Wait 3 seconds before next Markdown URL
        time.sleep(3)

if __name__ == '__main__':
    main()
