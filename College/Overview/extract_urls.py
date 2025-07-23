#!/usr/bin/env python3
import json
from pathlib import Path
import sys

INPUT = Path("college_overviews.json")
OUTPUT = Path("url.json")


def load_json(path):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            print(f"⚠️  Warning: {path} exists but is not valid JSON. Overwriting.")
    return []


def main():
    # 1) load input
    if not INPUT.exists():
        print(f"Error: {INPUT} not found.", file=sys.stderr)
        sys.exit(1)

    data = json.loads(INPUT.read_text())
    colleges = data.get("colleges", [])
    if not isinstance(colleges, list):
        print("Error: `colleges` key is missing or not a list.", file=sys.stderr)
        sys.exit(1)

    # 2) load existing output
    existing = load_json(OUTPUT)
    # normalize to list of dicts
    if not isinstance(existing, list):
        print(f"Error: {OUTPUT} should be a JSON array.", file=sys.stderr)
        sys.exit(1)

    seen_urls = {item.get("url") for item in existing if isinstance(item, dict)}

    # 3) collect new items
    new_items = []
    for c in colleges:
        url = c.get("url")
        cid = c.get("id")
        if not url or cid is None:
            continue
        if url in seen_urls:
            continue
        new_items.append({"id": cid, "url": url})

    # 4) append and write back
    if new_items:
        combined = existing + new_items
        OUTPUT.write_text(json.dumps(combined, indent=2))
        print(f"✅ Added {len(new_items)} new URL(s) to {OUTPUT}.")
    else:
        print("ℹ️  No new URLs to add.")


if __name__ == "__main__":
    main()
