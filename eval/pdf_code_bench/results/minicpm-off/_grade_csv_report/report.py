#!/usr/bin/env python3
import argparse
import csv
import json
import sys

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    
    parser = argparse.ArgumentParser(description="Group and sum CSV data")
    parser.add_argument("FILE", help="Path to CSV file")
    parser.add_argument("--group", required=True, help="Column to group by")
    parser.add_argument("--sum", required=True, help="Column to sum")
    parser.add_argument("--sort", choices=["total", "key"], default="key",
                        help="Sort by 'total' (descending) or 'key' (ascending, default)")
    parser.add_argument("--top", type=int, help="Keep only top N groups after sorting")
    
    args = parser.parse_args(argv)
    
    # Check if file exists
    import os
    if not os.path.isfile(args.FILE):
        print(f"Error: File '{args.FILE}' not found", file=sys.stderr)
        sys.exit(2)
    
    # Read CSV
    with open(args.FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if args.group not in reader.fieldnames or args.sum not in reader.fieldnames:
            print(f"Error: Column '{args.group}' or '{args.sum}' not found in CSV header", file=sys.stderr)
            sys.exit(2)
        
        groups = {}
        skipped = 0
        
        for row in reader:
            key = row[args.group]
            value = row[args.sum]
            
            # Skip rows where sum value is empty or not a number
            if value == '' or value is None:
                skipped += 1
                continue
            
            try:
                num = float(value)
            except ValueError:
                skipped += 1
                continue
            
            if key not in groups:
                groups[key] = {'total': 0.0, 'rows': 0}
            groups[key]['total'] += num
            groups[key]['rows'] += 1
        
        # Process totals: int if whole, else float rounded to 2 decimals
        processed_groups = []
        for key, data in groups.items():
            total = data['total']
            if total == int(total):
                total = int(total)
            else:
                total = round(total, 2)
            processed_groups.append({'key': key, 'total': total, 'rows': data['rows']})
        
        # Sort
        if args.sort == "key":
            processed_groups.sort(key=lambda x: x['key'])
        elif args.sort == "total":
            processed_groups.sort(key=lambda x: (-x['total'], x['key']))
        
        # Top N
        if args.top is not None and args.top > 0:
            processed_groups = processed_groups[:args.top]
        
        result = {"groups": processed_groups, "skipped": skipped}
        print(json.dumps(result))
    
    return 0

if __name__ == "__main__":
    sys.exit(main())