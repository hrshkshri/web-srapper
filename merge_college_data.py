import json
from pathlib import Path

# ─── CONFIG ─────────────────────────────────────────────────────────────
OVERVIEW_FILE = Path("college_overviews.json")
ADMISSIONS_FILE = Path("admissions.json")
COURSES_FILE = Path("courses.json")
SCHOLARSHIPS_FILE = Path("scholarships.json")
OUTPUT_FILE = Path("merged_colleges.json")

# ─── LOAD ALL DATA ──────────────────────────────────────────────────────
with open(OVERVIEW_FILE, encoding="utf-8") as f:
    overview_data = json.load(f)

with open(ADMISSIONS_FILE, encoding="utf-8") as f:
    admissions_data = json.load(f)

with open(COURSES_FILE, encoding="utf-8") as f:
    courses_data = json.load(f)

with open(SCHOLARSHIPS_FILE, encoding="utf-8") as f:
    scholarships_data = json.load(f)

# ─── INDEX BY URL FOR FAST LOOKUP ───────────────────────────────────────
admissions_dict = {
    entry["url"]: entry.get("admissions", []) for entry in admissions_data
}

courses_dict = {entry["url"]: entry.get("courses", []) for entry in courses_data}

scholarships_dict = {
    entry["url"]: entry.get("scholarships", []) for entry in scholarships_data
}

# ─── MERGE ──────────────────────────────────────────────────────────────
merged = []

for college in overview_data.get("colleges", []):
    url = college.get("url")
    merged_entry = {
        "id": college.get("id"),
        "url": url,
        "name": college.get("name"),
        "location": college.get("location"),
        "overview": college.get("overview", {}),
    }

    # attach admissions if we have them
    if url in admissions_dict:
        merged_entry["admissions"] = admissions_dict[url]

    # attach courses if we have them
    if url in courses_dict:
        merged_entry["courses"] = courses_dict[url]

    # attach scholarships if we have them
    if url in scholarships_dict:
        merged_entry["scholarships"] = scholarships_dict[url]

    merged.append(merged_entry)

# ─── WRITE OUT ──────────────────────────────────────────────────────────
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(merged, f, indent=2, ensure_ascii=False)

print(f"✅ Merged data written to {OUTPUT_FILE}")
