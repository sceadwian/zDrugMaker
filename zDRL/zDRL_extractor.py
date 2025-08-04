#!/usr/bin/env python3
import os
import re
import csv
import sys

def parse_sessions(text):
    # split into blocks beginning with “Start Date:”
    chunks = re.split(r'(?=Start Date:)', text)
    for chunk in chunks:
        if not chunk.strip():
            continue

        # extract the simple fields as before
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

        # now pull out the T() values
        lines = chunk.splitlines()
        # find the line exactly equal to "T:" (ignoring leading/trailing whitespace)
        try:
            t_index = next(i for i, L in enumerate(lines) if L.strip() == 'T:')
        except StopIteration:
            t_values = []
        else:
            t_values = []
            # every subsequent line that starts with whitespace+digit+":" is a T‑line
            for L in lines[t_index+1:]:
                if re.match(r'^\s*\d+:', L):
                    # remove the "123:" prefix, split on whitespace
                    vals = L.split(':',1)[1].strip().split()
                    t_values.extend(vals)
                else:
                    break

        # build the session dict
        session = {k: v.group(1) for k, v in m.items()}
        session['IRT_List'] = ';'.join(t_values)
        yield session

def choose_file():
    files = [f for f in os.listdir('.') if os.path.isfile(f)]
    if not files:
        raise FileNotFoundError("No files found in current directory.")
    print("Files in current directory:")
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
    print("\n=== DRL Output Parser ===\n")
    infile = choose_file()
    print(f"\nParsing → {infile}\n")

    with open(infile, 'r', encoding='utf-8') as f:
        text = f.read()

    sessions = list(parse_sessions(text))
    if not sessions:
        raise ValueError("No valid DRL sessions found in the chosen file.")

    # build the output filename
    root, _ = os.path.splitext(infile)
    outfile = root + '.csv'

    # write CSV with a consistent set of columns
    fieldnames = [
        'Date','AnimalID','StartTime','EndTime',
        'TotalResponses','ReinforcedResponses','IRT_List'
    ]
    with open(outfile, 'w', newline='', encoding='utf-8') as csvf:
        writer = csv.DictWriter(csvf, fieldnames=fieldnames)
        writer.writeheader()
        for sess in sessions:
            writer.writerow(sess)

    print(f"✅ Summary written to {outfile}")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
    finally:
        input("\nPress Enter to exit...")
