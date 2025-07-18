#!/usr/bin/env python3
import json
import sys

# ==== configure your input file path here ====
INPUT_PATH = "college_overviews.json"  # wrapped JSON with "colleges": [ … ]
# ============================================


def count_colleges(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # get the list under "colleges" and print its length
    print(len(data.get("colleges", [])))


if __name__ == "__main__":
    count_colleges(INPUT_PATH)
