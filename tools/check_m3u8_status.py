#!/usr/bin/env python3

import csv
import time
import requests

# Settings: configure file path and delay here
CSV_FILE = 'tools/get_m3u8_url_list.csv'
DELAY_SECONDS = 1


def main():
    # Read URLs from CSV file into a list
    urls = []
    with open(CSV_FILE, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if row:
                urls.append(row[0].strip())

    valid_urls = []

    # Iterate over the list, check each URL, and collect only working ones
    for url in urls:
        try:
            # Send HTTP GET request to the URL
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                valid_urls.append(url)
        except requests.RequestException as e:
            pass        
        time.sleep(DELAY_SECONDS)

    # Overwrite the CSV file with only the valid URLs
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        for valid_url in valid_urls:
            writer.writerow([valid_url])

    # Print the remaining working URLs
    print('\nОставшиеся рабочие URL (записаны обратно в файл):')
    for u in valid_urls:
        print(u)


if __name__ == '__main__':
    main()
