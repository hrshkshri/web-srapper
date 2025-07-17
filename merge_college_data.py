import json

# Load the data from the three JSON files
with open("college_overviews.json") as f:
    overview_data = json.load(f)

with open("admissions.json") as f:
    admissions_data = json.load(f)

with open("courses.json") as f:
    courses_data = json.load(f)

# Create dictionaries for faster lookup by URL
admissions_dict = {college["url"]: college for college in admissions_data}
courses_dict = {college["url"]: college for college in courses_data}

# Merge data based on URL
merged_colleges = []

for college in overview_data["colleges"]:
    url = college["url"]
    merged_entry = {
        "id": college.get("id"),
        "url": url,
        "name": college.get("name"),
        "location": college.get("location"),
        "overview": college.get("overview", {}),
    }

    # Add admissions data if available
    if url in admissions_dict:
        merged_entry["admissions"] = admissions_dict[url].get("admissions", [])

    # Add courses data if available
    if url in courses_dict:
        merged_entry["courses"] = courses_dict[url].get("courses", [])

    merged_colleges.append(merged_entry)

# Save the merged output
with open("merged_colleges.json", "w") as f:
    json.dump(merged_colleges, f, indent=2)

print("✅ Merged data saved to 'merged_colleges.json'")
