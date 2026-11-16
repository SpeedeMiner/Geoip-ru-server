"""Strict validation for the builder's per-source record counts."""
import csv

HEADER = ["SOURCE", "RU_CATEGORY_CIDR_INPUTS", "CANDIDATE_CIDR_INPUTS",
          "PRIVATE_CIDR_INPUTS", "OTHER_EVIDENCE_CIDR_INPUTS", "TOTAL_CIDR_INPUTS"]


def read_source_counts(path):
    counts = {}
    with open(path, encoding="utf-8", newline="") as source:
        rows = csv.reader(source, delimiter="\t", strict=True)
        if next(rows, None) != HEADER:
            raise ValueError("unexpected source-count schema")
        for row in rows:
            if (len(row) != 6 or not row[0] or row[0] != row[0].strip()
                    or row[0] in counts or any(not v.isascii() or not v.isdigit() for v in row[1:])):
                raise ValueError(f"malformed or duplicate source-count row at line {rows.line_num}")
            values = [int(v) for v in row[1:]]
            if sum(values[:4]) != values[4]:
                raise ValueError(f"source-count row total mismatch at line {rows.line_num}")
            counts[row[0]] = row
    if "TOTAL" not in counts:
        raise ValueError("source-count TOTAL row is missing")
    totals = [sum(int(row[i]) for name, row in counts.items() if name != "TOTAL") for i in range(1, 6)]
    if totals != [int(value) for value in counts["TOTAL"][1:]]:
        raise ValueError("source-count totals do not reconcile")
    return counts
