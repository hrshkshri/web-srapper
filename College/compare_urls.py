#!/usr/bin/env python3
import json
from collections import Counter

# ==== Configure your input/output file paths ====
JSONL_PATH = "./Courses/with_courses.jsonl"
JSON_PATH = "./Overview/college_overviews.json"
OUTPUT_PATH = "url_comparison_report.json"
# ================================================


def load_urls_from_jsonl(path):
    urls = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                obj = json.loads(line.strip())
                url = obj.get("url")
                if url:
                    urls.add(url)
    return urls


def load_urls_from_json(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        college.get("url", "")
        for college in data.get("colleges", [])
        if "url" in college
    }


def compare_and_save(
    urls1,
    urls2,
    label1="File 1",
    label2="File 2",
    output_file="url_comparison_report.json",
):
    only_in_1 = sorted(urls1 - urls2)
    only_in_2 = sorted(urls2 - urls1)
    common = sorted(urls1 & urls2)

    result = {
        "summary": {
            label1: len(urls1),
            label2: len(urls2),
            "common_urls": len(common),
            f"missing_in_{label2}": len(only_in_1),
            f"missing_in_{label1}": len(only_in_2),
        },
        f"only_in_{label1}": only_in_1,
        f"only_in_{label2}": only_in_2,
        "common_urls": common,
    }

    with open(output_file, "w", encoding="utf-8") as out:
        json.dump(result, out, indent=2)

    print("✅ Comparison complete. Report saved to:", output_file)


if __name__ == "__main__":
    jsonl_urls = load_urls_from_jsonl(JSONL_PATH)
    json_urls = load_urls_from_json(JSON_PATH)
    compare_and_save(
        jsonl_urls,
        json_urls,
        label1="with_courses.jsonl",
        label2="college_overviews.json",
        output_file=OUTPUT_PATH,
    )
