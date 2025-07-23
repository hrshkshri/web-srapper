import json


def transform_jsonl(input_file_path, output_file_path):
    transformed = []

    with open(input_file_path, "r", encoding="utf-8") as infile:
        for line in infile:
            entry = json.loads(line.strip())
            transformed_entry = {
                "counter": entry.get("counter"),
                "id": entry.get("id"),
                "url": entry.get("url"),
                "name": entry.get("name"),
                "location": entry.get("location"),
                "overview": {},
            }
            for key, value in entry.get("overview", {}).items():
                if isinstance(value, list) and len(value) >= 2:
                    transformed_entry["overview"][key] = value
            transformed.append(transformed_entry)

    with open(output_file_path, "w", encoding="utf-8") as outfile:
        json.dump(transformed, outfile, indent=2)


# Example usage:
transform_jsonl("college_overviews_data.json", "output.json")
