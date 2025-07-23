import json


def transform_courses_jsonl(input_file_path, output_file_path):
    transformed = []

    with open(input_file_path, "r", encoding="utf-8") as infile:
        for line in infile:
            if not line.strip():
                continue  # skip empty lines

            entry = json.loads(line.strip())

            # Prepare the main college structure
            clean_entry = {
                "id": entry.get("id"),
                "url": entry.get("url"),
                "name": entry.get("name"),
                "location": entry.get("location"),
                "courses": [],
            }

            # Process each course
            for course in entry.get("courses", []):
                if "title" in course:
                    clean_entry["courses"].append(
                        {
                            "title": course.get("title"),
                            "program": course.get("program", {}),
                            "fees": course.get("fees", {}),
                            "extras": course.get("extras", {}),
                        }
                    )

            transformed.append(clean_entry)

    # Save transformed data to JSON file
    with open(output_file_path, "w", encoding="utf-8") as outfile:
        json.dump(transformed, outfile, indent=2)


# ==== Example usage ====
# Make sure to replace these with your actual file paths
transform_courses_jsonl("with_courses.jsonl", "clean_courses_output.json")
