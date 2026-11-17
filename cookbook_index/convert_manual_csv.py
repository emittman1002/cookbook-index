#!/usr/bin/env python
"""Convert manual-solution/input.csv to output/new-input.csv format.

Reformats the manual CSV (Recipe,Page with bracket markers) to match
the output/recipe-names.csv format (RecipeName,RecipePage,IndexPage),
using vertical bars as delimiters.

Index Page markers like `[p1002],` are used to determine the IndexPage
for each recipe entry, but are NOT included in the output CSV.
"""
import re
import csv
from cookbook_index import TOP_DIR, WORK_DIR


def parse_input_csv(filename: str) -> list:
    """Parse manual-solution/input.csv into a list of recipe entries.

    Format:
      - Bracket markers like [p1002], (csv.reader splits into ['[p1002]', ''])
      - Recipe lines like RecipeName,Page (csv.reader splits into ['RecipeName', 'Page'])
    """
    index_marker_pattern = re.compile(r"^\[\s*p\s*(\d+)\s*\]$")
    current_index = None
    entries = []
    with open(filename, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if len(row) < 1:
                continue

            raw = row[0].strip()

            # Index Page entries like [p1002], are used only for tracking
            # IndexPage values, NOT written to the output CSV.
            if index_marker_pattern.match(raw):
                current_index = int(index_marker_pattern.match(raw).group(1))
                continue

            if current_index is None:
                current_index = 0

            recipe = raw
            # Parse the page number from the second column
            if len(row) > 1:
                page_str = row[1].strip()
            else:
                page_str = ""
            try:
                page = int(page_str)
            except ValueError:
                page = 0
            entries.append((recipe, page, current_index))
    return entries


def main():
    input_path = f"{TOP_DIR}/manual-solution/input.csv"
    output_path = f"{WORK_DIR}/manual-input.csv"

    entries = parse_input_csv(input_path)

    sorted_entries = sorted(entries, key=lambda e: (e[2], e[0]))
    print(f"Parsed {len(entries)} entries from {input_path}")

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="|")
        writer.writerow(["RecipeName", "RecipePage", "IndexPage"])
        for recipe, page, index in sorted_entries:
            writer.writerow([recipe, page, index])

    print(f"Wrote {len(sorted_entries)} entries to {output_path}")


if __name__ == "__main__":
    main()
