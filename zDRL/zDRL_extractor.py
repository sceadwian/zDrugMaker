#!/usr/bin/env python3
# v2 2025-0908 - added pellet cap on top of time cap to schedule and fixed what directory this thing looks for data.
# v3 2025-1006 - corrected the binned data sorter so that time bins are represented in seconds instead. function bin_irts(irt_strings) has been modified for this and it now filters 0.200 as well
import os
import re
import csv
import sys

# ----- Configuration: IRT bins -----
BIN_LABELS = [
    "0-2s","2-4s","4-6s","6-8s","8-10s","10-12s","12-14s","14-16s",
    "16-18s","18-20s","20-22s","22-24s","24-26s","26-28s","28-30s","30-32s","32-34s"
]
# Corresponding numeric edges (seconds). For all bins except the last: start <= x < end
# For the last bin, we include the upper edge: start <= x <= end
BIN_EDGES = [(0,2),(2,4),(4,6),(6,8),(8,10),(10,12),(12,14),(14,16),
             (16,18),(18,20),(20,22),(22,24),(24,26),(26,28),(28,30),(30,32),(32,34)]

def parse_sessions(text):
    """Yield session dicts with parsed fields and raw IRT values (as strings)."""
    chunks = re.split(r'(?=Start Date:)', text)
    for chunk in chunks:
        if not chunk.strip():
            continue

        m = {
            'Date':                re.search(r'Start Date:\s*(\S+)', chunk),
            'AnimalID':            re.search(r'Box:\s*(\d+)', chunk),
            'StartTime':           re.search(r'Start Time:\s*([\d:]+)', chunk),
            'EndTime':             re.search(r'End Time:\s*([\d:]+)', chunk),
            'TotalResponses':      re.search(r'^\s*A:\s*([\d.]+)', chunk, re.MULTILINE),
            'ReinforcedResponses': re.search(r'^\s*B:\s*([\d.]+)', chunk, re.MULTILINE),
        }
        if not all(m.values()):
            continue

        # Pull out IRT values after the "T:" block
        lines = chunk.splitlines()
        try:
            t_index = next(i for i, L in enumerate(lines) if L.strip() == 'T:')
        except StopIteration:
            t_values_raw = []
        else:
            t_values_raw = []
            for L in lines[t_index+1:]:
                if re.match(r'^\s*\d+:', L):
                    vals = L.split(':', 1)[1].strip().split()
                    t_values_raw.extend(vals)
                else:
                    break

        session = {k: v.group(1) for k, v in m.items()}
        session['IRT_values_raw'] = t_values_raw
        yield session

def bin_irts(irt_strings):
    """Convert list of IRT strings to counts per configured bins."""
    counts = {label: 0 for label in BIN_LABELS}

    # Convert strings (tenths of a second) to floats in *seconds*
    irts = []
    for s in irt_strings:
        s = s.strip().rstrip(',;')
        try:
            v = float(s) * 0.1  # Convert tenths of seconds → seconds
            # Skip made up 0.2 markers for reinforcers
            if abs(v - 0.02) < 1e-6:
                continue
            irts.append(v)
        except ValueError:
            continue

    # Tally into bins
    for v in irts:
        # Ignore negative or > last upper edge values
        # (Change this behavior if you want an overflow bin)
        placed = False
        for i, (lo, hi) in enumerate(BIN_EDGES):
            if i < len(BIN_EDGES) - 1:
                if lo <= v < hi:
                    counts[BIN_LABELS[i]] += 1
                    placed = True
                    break
            else:
                # Last bin: include the upper bound
                if lo <= v <= hi:
                    counts[BIN_LABELS[i]] += 1
                    placed = True
                    break
        # If not placed, we simply ignore (out-of-range)
    return counts

def choose_file(script_dir):
    files = [f for f in os.listdir(script_dir) if os.path.isfile(os.path.join(script_dir, f))]
    if not files:
        raise FileNotFoundError("No files found in script directory.")
    print("Files in script directory:")
    for i, fn in enumerate(files, start=1):
        print(f"  {i}. {fn}")
    while True:
        choice = input(f"\nSelect a file by number (1–{len(files)}): ").strip()
        if not choice.isdigit():
            print("▶ Please enter a valid number.")
            continue
        idx = int(choice)
        if 1 <= idx <= len(files):
            return files[idx-1]
        print(f"▶ Number must be between 1 and {len(files)}.")

def main():
    print("\n=== DRL Output Parser (IRT-binned) ===\n")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    infile = choose_file(script_dir)
    print(f"\nParsing → {infile}\n")

    with open(os.path.join(script_dir, infile), 'r', encoding='utf-8') as f:
        text = f.read()

    sessions = list(parse_sessions(text))
    if not sessions:
        raise ValueError("No valid DRL sessions found in the chosen file.")

    root, _ = os.path.splitext(infile)
    outfile = os.path.join(script_dir, root + '.csv')

    # CSV columns: session metadata + IRT bin counts
    fieldnames = [
        'Date','AnimalID','StartTime','EndTime','TotalResponses','ReinforcedResponses'
    ] + BIN_LABELS

    with open(outfile, 'w', newline='', encoding='utf-8') as csvf:
        writer = csv.DictWriter(csvf, fieldnames=fieldnames)
        writer.writeheader()
        for sess in sessions:
            row = {
                'Date': sess['Date'],
                'AnimalID': sess['AnimalID'],
                'StartTime': sess['StartTime'],
                'EndTime': sess['EndTime'],
                'TotalResponses': sess['TotalResponses'],
                'ReinforcedResponses': sess['ReinforcedResponses'],
            }
            counts = bin_irts(sess.get('IRT_values_raw', []))
            row.update(counts)
            writer.writerow(row)

    print(f"✅ Summary written to {outfile}")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
    finally:
        input("\nPress Enter to exit...")