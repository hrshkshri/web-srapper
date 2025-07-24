#!/usr/bin/env python3
"""
compare_urls.py

Load two JSON files, each containing a top‐level array of objects with "id" and "url" keys.
Write out a new JSON file containing those entries from the first file whose URLs are
not found in the second file.
"""

import json

# ─── Configuration ────────────────────────────────────
# Path to the JSON file containing "missing" URLs (array of { "id":…, "url":… } objects)
MISSING_PATH = "missing_in_Courses.json"
# Path to the JSON file containing all course URLs (array of { "id":…, "url":… } objects)
COURSES_PATH = "url_course.json"
# Path where the filtered result will be written
OUTPUT_PATH = "urls_not_in_course.json"
# ──────────────────────────────────────────────────────


def load_array(path):
    """
    Load a JSON file that contains a single top‑level array of objects.
    Returns the parsed Python list.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    # Load both files as Python lists of dicts
    missing = load_array(MISSING_PATH)
    courses = load_array(COURSES_PATH)

    # Build a set of all URLs present in the courses file
    course_urls = {entry["url"] for entry in courses if "url" in entry}

    # Filter the "missing" list to only those entries whose URL is NOT in course_urls
    diff = [
        entry
        for entry in missing
        if entry.get("url") and entry["url"] not in course_urls
    ]

    # Write out the filtered list (same format: array of { "id":…, "url":… } objects)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as out:
        json.dump(diff, out, indent=2, ensure_ascii=False)

    print(f"Found {len(diff)} URLs not in course list.")
    print(f"Output written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
