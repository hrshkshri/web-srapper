#!/usr/bin/env python3
import json
from collections import Counter

# ==== configure your file path here ====
INPUT_PATH = "with_courses.jsonl"
# =======================================


def find_duplicate_urls_from_jsonl(path):
    urls = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                obj = json.loads(line.strip())
                url = obj.get("url")
                if url:
                    urls.append(url)

    total_urls = len(urls)
    unique_urls = len(set(urls))
    counts = Counter(urls)
    duplicates = {url: cnt for url, cnt in counts.items() if cnt > 1}

    print(f"Total URLs:  {total_urls}")
    print(f"Unique URLs: {unique_urls}")
    print(f"Duplicate URLs: {len(duplicates)}\n")

    if not duplicates:
        print("✅ All URLs are unique.")
    else:
        print("⚠️ Found duplicate URLs:")
        for url, cnt in duplicates.items():
            print(f"  {url} — {cnt} times")


if __name__ == "__main__":
    find_duplicate_urls_from_jsonl(INPUT_PATH)
