import json
from pathlib import Path

# ─── CONFIG ─────────────────────────────────────────────────────────────
OVERVIEW_FILE = Path("./Overview/college_overviews.json")
ADMISSIONS_FILE = Path("./Admission/admissions.json")
COURSES_FILE = Path("./Courses/clean_courses_output.json")
SCHOLARSHIPS_FILE = Path("./Scholarships/scholarships.json")
OUTPUT_FILE = Path("./Output/merged_colleges.json")

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

missing_admissions = []
missing_courses = []
missing_scholarships = []

for college in overview_data.get("colleges", []):
    url = college.get("url")
    merged_entry = {
        "id": college.get("id"),
        "url": url,
        "name": college.get("name"),
        "location": college.get("location"),
        "overview": college.get("overview", {}),
    }

    # attach admissions
    if url in admissions_dict:
        merged_entry["admissions"] = admissions_dict[url]
    else:
        missing_admissions.append(url)

    # attach courses
    if url in courses_dict:
        merged_entry["courses"] = courses_dict[url]
    else:
        missing_courses.append(url)

    # attach scholarships
    if url in scholarships_dict:
        merged_entry["scholarships"] = scholarships_dict[url]
    else:
        missing_scholarships.append(url)

    merged.append(merged_entry)

# ─── WRITE OUT ──────────────────────────────────────────────────────────
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(merged, f, indent=2, ensure_ascii=False)

# ─── LOG SUMMARY ────────────────────────────────────────────────────────
print("\n✅ Merge Complete!")
print(f"📄 Total colleges in overview: {len(overview_data.get('colleges', []))}")
print(f"📦 Total merged records: {len(merged)}")

print(f"📭 Missing admissions: {len(missing_admissions)}")
print(f"📭 Missing courses: {len(missing_courses)}")
print(f"📭 Missing scholarships: {len(missing_scholarships)}")

print(f"\n📁 Output written to: {OUTPUT_FILE}")
