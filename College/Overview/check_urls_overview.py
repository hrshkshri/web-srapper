#!/usr/bin/env python3
import json
import sys
from collections import Counter

# ==== configure your file path here ====
INPUT_PATH = "college_overviews.json"
# =======================================


def find_duplicate_urls(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Extract all URLs
    urls = [college.get("url", "") for college in data.get("colleges", [])]

    total_urls = len(urls)
    unique_urls = len(set(urls))

    # Count occurrences
    counts = Counter(urls)

    # Filter to those URLs seen more than once
    duplicates = {url: cnt for url, cnt in counts.items() if cnt > 1}

    # Print summary
    print(f"Total URLs:  {total_urls}")
    print(f"Unique URLs: {unique_urls}")
    print(f"Duplicate URLs: {len(duplicates)}\n")

    if not duplicates:
        print("All URLs are unique.")
    else:
        print("Found duplicate URLs:")
        for url, cnt in duplicates.items():
            print(f"  {url} — {cnt} times")


if __name__ == "__main__":
    find_duplicate_urls(INPUT_PATH)
