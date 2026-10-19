#!/usr/bin/env python3
"""Report: group a CSV by one column, sum another, print JSON.

Usage:
    python report.py FILE --group COLUMN --sum COLUMN [--sort total|key] [--top N]
"""

import argparse
import csv
import json
import sys


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="report.py",
        description="Group a CSV file by a column, sum a numeric column, "
                    "and print a JSON report to stdout.",
    )
    parser.add_argument("file", help="Path to the CSV file (must have a header row)")
    parser.add_argument("--group", required=True,
                        help="Column name to group rows by")
    parser.add_argument("--sum", dest="sumcol", required=True,
                        help="Column name to sum (numeric values only)")
    parser.add_argument("--sort", choices=["key", "total"], default="key",
                        help="Sort order: 'key' (ascending, default) or "
                             "'total' (descending, ties by key)")
    parser.add_argument("--top", type=int, default=None, metavar="N",
                        help="Keep only the first N groups after sorting")
    return parser.parse_args(argv)


def fmt_total(value):
    """Return an int when the value is whole, else a float rounded to 2 decimals."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return round(value, 2)


def build_report(rows, group_col, sum_col):
    """Group rows, sum values, count skipped rows. Returns (groups, skipped)."""
    totals = {}
    counts = {}
    order = []
    skipped = 0
    for row in rows:
        key = row.get(group_col)
        if key is None:
            continue
        raw = row.get(sum_col)
        if raw is None:
            skipped += 1
            continue
        raw = raw.strip()
        if raw == "":
            skipped += 1
            continue
        try:
            value = float(raw)
        except ValueError:
            skipped += 1
            continue
        if key not in totals:
            totals[key] = 0.0
            counts[key] = 0
            order.append(key)
        totals[key] += value
        counts[key] += 1

    groups = [
        {"key": k, "total": fmt_total(totals[k]), "rows": counts[k]}
        for k in order
    ]
    return groups, skipped


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = parse_args(argv)

    if args.top is not None and args.top < 0:
        print("error: --top must be >= 0", file=sys.stderr)
        return 2

    try:
        with open(args.file, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            if fieldnames is None:
                print(f"error: {args.file}: empty file (no header)", file=sys.stderr)
                return 2
            if args.group not in fieldnames:
                print(f"error: unknown column: {args.group!r}", file=sys.stderr)
                return 2
            if args.sumcol not in fieldnames:
                print(f"error: unknown column: {args.sumcol!r}", file=sys.stderr)
                return 2
            rows = list(reader)
    except FileNotFoundError:
        print(f"error: file not found: {args.file}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: cannot read {args.file}: {exc}", file=sys.stderr)
        return 2

    groups, skipped = build_report(rows, args.group, args.sumcol)

    if args.sort == "total":
        groups.sort(key=lambda g: (-g["total"], g["key"]))
    else:
        groups.sort(key=lambda g: g["key"])

    if args.top is not None:
        groups = groups[:args.top]

    print(json.dumps({"groups": groups, "skipped": skipped}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
