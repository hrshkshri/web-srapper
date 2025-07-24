import json
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
INPUT_FILE = "scholarships.json"
OUTPUT_FILE = "unique_scholarships.json"


def extract_unique_scholarship_urls():
    # 1) Load the full colleges JSON
    with open(INPUT_FILE, encoding="utf-8") as f:
        colleges = json.load(f)

    # 2) Deduplicate on (college_id, url)
    seen = set()
    records = []
    for college in colleges:
        cid = college.get("id")
        for course_group in college.get("scholarships", []):
            for sch in course_group.get("scholarships", []):
                url = sch.get("url")
                if cid is None or not url:
                    continue
                key = (cid, url)
                if key in seen:
                    continue
                seen.add(key)
                records.append({"id": cid, "url": url})

    # 3) Write out
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    print(f"Loaded {len(colleges)} colleges from {INPUT_FILE}")
    print(
        f"Total scholarship URLs found: {sum(len(course_group.get('scholarships', [])) for college in colleges for course_group in college.get('scholarships', []))}"
    )
    print(f"Wrote {len(records)} unique (id, url) records to {OUTPUT_FILE}")


if __name__ == "__main__":
    extract_unique_scholarship_urls()
