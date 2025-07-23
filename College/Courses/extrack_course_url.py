#!/usr/bin/env python3
import json
from pathlib import Path
import sys

# ==== configure your file paths here ====
INPUT = Path("../Courses/clean_courses_output.json")
OUTPUT = Path("url_course.json")
# ========================================


def load_json(path):
    """Load JSON array from `path`, or return [] if file is missing/invalid."""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
            else:
                print(f"⚠️  Warning: {path} contains non-array JSON; resetting to [].")
        except json.JSONDecodeError:
            print(f"⚠️  Warning: {path} exists but is not valid JSON. Overwriting.")
    return []


def main():
    # 1) Load input
    if not INPUT.exists():
        print(f"❌ Error: Input file not found at {INPUT}", file=sys.stderr)
        sys.exit(1)

    raw = json.loads(INPUT.read_text(encoding="utf-8"))
    colleges = raw.get("colleges") if isinstance(raw, dict) else raw
    if not isinstance(colleges, list):
        print(
            "❌ Error: Expected a list of colleges (or an object with 'colleges' list).",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"🔍 Found {len(colleges)} college entries in input.")

    # 2) Load existing output
    existing = load_json(OUTPUT)
    print(f"📂 Output file {OUTPUT} currently has {len(existing)} entries.")

    seen_urls = {
        item.get("url")
        for item in existing
        if isinstance(item, dict) and item.get("url")
    }

    # 3) Collect new items
    new_items = []
    for c in colleges:
        url = c.get("url")
        cid = c.get("id")
        if not url or cid is None:
            continue
        if url in seen_urls:
            continue
        new_items.append({"id": cid, "url": url})

    print(f"➕ Identified {len(new_items)} new URL(s) to add.")

    # 4) Append and write back (only if there are new items)
    if new_items:
        combined = existing + new_items
        OUTPUT.write_text(json.dumps(combined, indent=2), encoding="utf-8")
        print(
            f"✅ Wrote {len(new_items)} new entries; total is now {len(combined)} URLs in {OUTPUT}."
        )
    else:
        print("ℹ️  No new URLs to add; output file is up to date.")


if __name__ == "__main__":
    main()
