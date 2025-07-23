#!/usr/bin/env python3
import json
from pathlib import Path
from collections import Counter

# ==== configure your file paths here ====
FILE1 = "url1.json"
FILE2 = "url2.json"
OUTPUT = "courses_vs_url.json"
# ========================================


def load_items(path):
    """Load a JSON file containing a top‐level list of objects with at least a "url" key."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} must be a top‑level JSON array")
    return data


def main():
    # Load both lists
    items1 = load_items(FILE1)
    items2 = load_items(FILE2)

    # Log counts from each file
    count1 = len(items1)
    count2 = len(items2)
    print(f"{FILE1} has {count1} entries")
    print(f"{FILE2} has {count2} entries")

    # Build URL sets
    urls1 = {item.get("url") for item in items1 if item.get("url")}
    urls2 = {item.get("url") for item in items2 if item.get("url")}

    # Find items unique to one file or the other
    unique_urls = (urls1 - urls2) | (urls2 - urls1)
    unique_items = [item for item in items1 + items2 if item.get("url") in unique_urls]

    # Log the “minus both” count (i.e., the count of URLs only in one file)
    unique_count = len(unique_items)
    print(f"URLs only in one file: {unique_count}\n")

    # Write out the unique items
    out_path = Path(OUTPUT)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(unique_items, f, indent=2)

    print(f"Wrote {unique_count} unique entries to {OUTPUT}")


if __name__ == "__main__":
    main()
