#!/usr/bin/env python3
"""
MoSeq Usage Tool (no external libraries)

Menu options:
1) Analyze + export:
   - Relative occurrence (sum of per-treatment means by syllable)
   - Per-(syllable,treat) mean+SEM summary -> <base>_summary.txt
   - Consolidated long CSV of all rows -> <base>_allrows.csv
   - Optional ZIP with per-syllable CSVs inside (keeps folder tidy)

2) Create "wide" CSVs for ONE syllable:
   - <base>_syl<syllable>_wide_byID.csv  (rows=subjectID, columns=treats, values=mean usage)
   - <base>_syl<syllable>_wide_packed.csv (columns=treats, values stacked per treat; ignores IDs)

Run:
    python moseq_usage_tool.py
"""

import os
import sys
import csv
import math
import io
import zipfile

# ------------------ Utilities ------------------

def script_dir() -> str:
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()

def list_txt_files(folder: str):
    try:
        files = [f for f in os.listdir(folder) if f.lower().endswith(".txt") and os.path.isfile(os.path.join(folder, f))]
        files.sort()
        return files
    except Exception:
        return []

def detect_delimiter(header_line: str):
    if "\t" in header_line:
        return "\t"
    if "," in header_line:
        return ","
    return None  # fallback: whitespace split

def normalize_header_name(name: str) -> str:
    name = name.strip().lower()
    cleaned = []
    for ch in name:
        if ch.isalnum() or ch.isspace() or ch == "_":
            cleaned.append(ch)
    norm = "".join(cleaned)
    return " ".join(norm.split())

def build_header_index(raw_headers):
    """
    Map canonical keys -> column index, allowing flexible header labels.
    Required keys: subject, group, syllable, usage, treat
    """
    want = {
        "subject": ("subject", "subject id", "subjectid", "id"),
        "group": ("group",),
        "syllable": ("syllable", "behavioural syllable id", "behavioral syllable id", "syllable id"),
        "usage": ("usage", "amount the syllable is present", "count", "freq", "frequency"),
        "treat": ("treat", "treatment", "treatment group"),
    }

    norm_headers = [normalize_header_name(h) for h in raw_headers]
    idx_map = {}

    for key, candidates in want.items():
        found = None
        for i, h in enumerate(norm_headers):
            if h == key or h in candidates:
                found = i
                break
        if found is None:
            # last-resort contains-based match
            for i, h in enumerate(norm_headers):
                if any(c in h for c in (key,) + candidates):
                    found = i
                    break
        if found is None:
            return None
        idx_map[key] = found

    return idx_map

class OnlineStats:
    """Welford's algorithm for stable mean/variance (for SEM)."""
    __slots__ = ("n", "mean", "M2")
    def __init__(self):
        self.n = 0
        self.mean = 0.0
        self.M2 = 0.0
    def add(self, x: float):
        self.n += 1
        d = x - self.mean
        self.mean += d / self.n
        self.M2 += d * (x - self.mean)
    def mean_sem(self):
        if self.n == 0:
            return float("nan"), float("nan")
        if self.n == 1:
            return self.mean, 0.0
        var = self.M2 / (self.n - 1)
        return self.mean, math.sqrt(var / self.n)

def int_or_str_key(val: str):
    try:
        return (0, int(val))
    except Exception:
        return (1, val)

def press_enter(prompt: str = "Press Enter to continue..."):
    try:
        input(prompt)
    except (EOFError, KeyboardInterrupt):
        pass

def sanitize_for_filename(s: str) -> str:
    out = []
    for ch in s.strip():
        if ch.isalnum() or ch in ("-", "_", "."):
            out.append(ch)
        elif ch.isspace():
            out.append("_")
    return "".join(out) if out else "unknown"

# ------------------ Parsing ------------------

def parse_dataset(in_path: str):
    """
    Returns:
      stats: dict[(syll, treat)] -> OnlineStats of usage
      rows_by_syllable: dict[syll] -> list of (subject, group, treat, usage)
      all_rows: list of (subject, group, syll, treat, usage)
      skipped: int
    """
    if not os.path.isfile(in_path):
        raise FileNotFoundError(f"File not found: {in_path}")

    with open(in_path, "r", encoding="utf-8-sig", newline="") as f:
        first_line = f.readline()
        if not first_line:
            raise ValueError("Input file is empty.")
        delim = detect_delimiter(first_line)

    stats = {}
    rows_by_syllable = {}
    all_rows = []
    skipped = 0

    with open(in_path, "r", encoding="utf-8-sig", newline="") as f:
        if delim is not None:
            reader = csv.reader(f, delimiter=delim)
            header = next(reader, None)
            if not header:
                raise ValueError("Missing header row.")
            field_ix = build_header_index(header)
            if field_ix is None:
                delim = None
            else:
                for row in reader:
                    if not row:
                        continue
                    try:
                        subject = row[field_ix["subject"]].strip()
                        group = row[field_ix["group"]].strip()
                        syll   = row[field_ix["syllable"]].strip()
                        treat  = row[field_ix["treat"]].strip()
                        usage  = float(row[field_ix["usage"]])
                    except Exception:
                        skipped += 1
                        continue
                    stats.setdefault((syll, treat), OnlineStats()).add(usage)
                    rows_by_syllable.setdefault(syll, []).append((subject, group, treat, usage))
                    all_rows.append((subject, group, syll, treat, usage))

        if delim is None:
            # whitespace fallback
            f.seek(0)
            lines = f.readlines()
            if not lines:
                raise ValueError("Input file is empty.")
            header_cols = lines[0].strip().split()
            field_ix_ws = build_header_index(header_cols)
            if field_ix_ws is None:
                raise ValueError(
                    "Could not find required columns in header. "
                    "Expected: subject, group, syllable, usage, treat"
                )
            for line in lines[1:]:
                parts = line.strip().split()
                if not parts:
                    continue
                try:
                    subject = parts[field_ix_ws["subject"]]
                    group   = parts[field_ix_ws["group"]]
                    syll    = parts[field_ix_ws["syllable"]]
                    treat   = parts[field_ix_ws["treat"]]
                    usage   = float(parts[field_ix_ws["usage"]])
                except Exception:
                    skipped += 1
                    continue
                stats.setdefault((syll, treat), OnlineStats()).add(usage)
                rows_by_syllable.setdefault(syll, []).append((subject, group, treat, usage))
                all_rows.append((subject, group, syll, treat, usage))

    return stats, rows_by_syllable, all_rows, skipped

# ------------------ Features ------------------

def do_full_analysis(in_path: str):
    base, _ = os.path.splitext(in_path)
    stats, rows_by_syllable, all_rows, skipped = parse_dataset(in_path)

    # Per-(syll,treat) mean/SEM rows
    rows = []
    for (syll, treat), s in stats.items():
        mean, sem = s.mean_sem()
        rows.append((syll, treat, s.n, mean, sem))
    rows.sort(key=lambda r: (int_or_str_key(r[0]), r[1]))

    # Relative occurrence FIRST (sum of treat means per syllable)
    syll_total_mean = {}
    for (syll, treat, n, mean, sem) in rows:
        syll_total_mean[syll] = syll_total_mean.get(syll, 0.0) + (0.0 if math.isnan(mean) else mean)

    grand_total = sum(syll_total_mean.values())
    rel_rows = []
    for syll, total_mean in syll_total_mean.items():
        rel = (total_mean / grand_total) if grand_total > 0 else float("nan")
        rel_rows.append((syll, total_mean, rel, rel * 100 if not math.isnan(rel) else float("nan")))
    rel_rows.sort(key=lambda x: (-x[1], int_or_str_key(x[0])))

    # Print relative and pause
    print("# Relative occurrence by syllable across all treatments")
    print("# Based on sum of per-treatment means for each syllable")
    print("# Columns: syllable\ttotal_mean\trelative\tpercent")
    for syll, total_mean, rel, pct in rel_rows:
        if math.isnan(rel):
            print(f"{syll}\t{total_mean:.6f}\tNaN\tNaN")
        else:
            print(f"{syll}\t{total_mean:.6f}\t{rel:.6f}\t{pct:.2f}%")
    press_enter("\n(1/4) Review the relative occurrence above. Press Enter to continue to the per-treatment summary...")

    # Print summary table and write summary file
    summary_path = f"{base}_summary.txt"
    print("\n# Summary: usage by syllable and treatment")
    print("# Columns: syllable\ttreat\tn\tmean\tsem")
    for syll, treat, n, mean, sem in rows:
        print(f"{syll}\t{treat}\t{n}\t{mean:.6f}\t{sem:.6f}")

    with open(summary_path, "w", encoding="utf-8", newline="") as out_f:
        writer = csv.writer(out_f, delimiter="\t")
        writer.writerow(["syllable", "treat", "n", "mean", "sem"])
        for syll, treat, n, mean, sem in rows:
            writer.writerow([syll, treat, n, f"{mean:.6f}", f"{sem:.6f}"])
    print(f"\nWrote summary to: {summary_path}")

    press_enter("\n(2/4) Press Enter to write the consolidated CSV of all rows...")

    # Consolidated CSV with all rows
    all_rows.sort(key=lambda r: (int_or_str_key(r[2]), r[3], r[0]))  # by syllable, treat, subjectID
    allcsv_path = f"{base}_allrows.csv"
    with open(allcsv_path, "w", encoding="utf-8", newline="") as fcsv:
        writer = csv.writer(fcsv)
        writer.writerow(["subjectID", "group", "syllable", "treat", "usage"])
        for subject, group, syll, treat, usage in all_rows:
            writer.writerow([subject, group, syll, treat, f"{usage:.6f}"])
    print(f"Wrote consolidated CSV: {allcsv_path}")

    # Optional ZIP with per-syllable CSVs inside
    ans = input("\nWould you also like a single ZIP with per-syllable CSVs inside? [y/N]: ").strip().lower()
    if ans == "y":
        zip_path = f"{base}_per_syllables.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for syll in sorted(rows_by_syllable.keys(), key=int_or_str_key):
                safe_s = sanitize_for_filename(str(syll))
                inner_name = f"{os.path.basename(base)}_syl{safe_s}.csv"
                buf = io.StringIO()
                w = csv.writer(buf)
                w.writerow(["subjectID", "treat", "usage"])
                for subject, group, treat, usage in sorted(rows_by_syllable[syll], key=lambda x: (x[2], x[0])):
                    w.writerow([subject, treat, f"{usage:.6f}"])
                zf.writestr(inner_name, buf.getvalue())
        print(f"Created: {zip_path}")
    else:
        print("Skipped creating per-syllable ZIP.")

    if skipped:
        print(f"[Note] Skipped {skipped} malformed row(s).")

    press_enter("\n(3/4) Files written. Press Enter to review paths and finish...")

    print("\nDone.")
    print(f"Summary: {summary_path}")
    print(f"All rows: {allcsv_path}")
    if ans == "y":
        print(f"Per-syllable archive: {zip_path}")

    press_enter("\n(4/4) Press Enter to exit...")

def choose_syllable(rows_by_syllable):
    """Interactive picker: returns chosen syllable (string)."""
    sylls = sorted(rows_by_syllable.keys(), key=int_or_str_key)
    if not sylls:
        raise ValueError("No syllables found in dataset.")
    print("\nAvailable syllables:")
    for i, s in enumerate(sylls, 1):
        print(f"  {i}) {s}")
    while True:
        raw = input(f"Pick a syllable by number (1-{len(sylls)}) or type its exact ID: ").strip()
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(sylls):
                return str(sylls[idx - 1])
            else:
                print("Out of range.")
        elif raw:
            if raw in rows_by_syllable:
                return raw
            else:
                print("Not found. Please enter a valid number or exact syllable ID.")
        else:
            print("Please enter a choice.")

def do_wide_one_syllable(in_path: str):
    base, _ = os.path.splitext(in_path)
    stats, rows_by_syllable, all_rows, skipped = parse_dataset(in_path)
    syll = choose_syllable(rows_by_syllable)

    # ---------- (A) BY-ID wide table ----------
    # Build treat set and subject→treat aggregator (mean if multiple entries)
    treat_set = set()
    subj_treat_stats = {}  # subject -> treat -> OnlineStats
    for (subject, group, treat, usage) in rows_by_syllable.get(syll, []):
        treat_set.add(treat)
        subj_treat_stats.setdefault(subject, {}).setdefault(treat, OnlineStats()).add(usage)

    treat_cols = sorted(treat_set, key=int_or_str_key)
    subjects = sorted(subj_treat_stats.keys(), key=int_or_str_key)

    safe_s = sanitize_for_filename(str(syll))
    out_byid = f"{base}_syl{safe_s}_wide_byID.csv"
    with open(out_byid, "w", encoding="utf-8", newline="") as fcsv:
        writer = csv.writer(fcsv)
        writer.writerow(["subjectID"] + treat_cols)
        for subj in subjects:
            row = [subj]
            for t in treat_cols:
                st = subj_treat_stats[subj].get(t)
                if st is None or st.n == 0:
                    row.append("")  # blank for missing data
                else:
                    mean, _ = st.mean_sem()
                    row.append(f"{mean:.6f}")
            writer.writerow(row)

    # ---------- (B) PACKED wide table (ignores IDs) ----------
    # For each treat, collect *raw* usage values (no grouping by subject).
    treat_values = {}  # treat -> list[usage]
    for (subject, group, treat, usage) in rows_by_syllable.get(syll, []):
        treat_values.setdefault(treat, []).append(usage)

    treat_cols2 = sorted(treat_values.keys(), key=int_or_str_key)
    max_len = max((len(v) for v in treat_values.values()), default=0)

    out_packed = f"{base}_syl{safe_s}_wide_packed.csv"
    with open(out_packed, "w", encoding="utf-8", newline="") as fcsv:
        writer = csv.writer(fcsv)
        writer.writerow(treat_cols2)  # header = treat names only
        for i in range(max_len):
            row = []
            for t in treat_cols2:
                vals = treat_values.get(t, [])
                if i < len(vals):
                    row.append(f"{vals[i]:.6f}")
                else:
                    row.append("")  # pad shorter columns
            writer.writerow(row)

    print(f"\nWrote syllable-wide CSV (by ID): {out_byid}")
    print(f"Wrote syllable-wide CSV (packed, ignores IDs): {out_packed}")
    print(f"Subjects in byID table: {len(subjects)} | Treat columns: {len(treat_cols)}")
    print(f"Packed rows: {max_len} | Treat columns: {len(treat_cols2)}")

    if skipped:
        print(f"[Note] Skipped {skipped} malformed row(s).")

    press_enter("\nPress Enter to exit...")

# ------------------ UI: File chooser & Menu ------------------

def choose_input_file():
    base = script_dir()
    txts = list_txt_files(base)

    print("=== MoSeq Usage Tool ===")
    if txts:
        print("Found the following .txt files in the script folder:")
        for i, name in enumerate(txts, 1):
            print(f"  {i}) {name}")
        default_hint = " (press Enter for 1)" if len(txts) == 1 else ""
        choice = input(f"Enter number 1-{len(txts)} to select, or type a path{default_hint}: ").strip()
        if choice == "" and len(txts) == 1:
            return os.path.join(base, txts[0])
        if choice.isdigit():
            num = int(choice)
            if 1 <= num <= len(txts):
                return os.path.join(base, txts[num - 1])
            else:
                print("Invalid selection number.")
        if choice:
            return choice
        print("No valid selection provided.")
    else:
        print("No .txt files found in the script folder.")
    path = input("Please type the path to the input .txt file: ").strip()
    return path

def main_menu() -> str:
    print("\nSelect an option:")
    print("  1) Analyze + export (relative occurrence, summary, consolidated CSV, optional ZIP)")
    print("  2) Create wide CSVs for one syllable (byID + packed, ignores IDs)")
    print("  0) Exit")
    while True:
        c = input("Enter choice [1/2/0]: ").strip()
        if c in {"1", "2", "0"}:
            return c
        print("Please enter 1, 2, or 0.")

def main():
    try:
        choice = main_menu()
        if choice == "0":
            print("Goodbye.")
            return

        in_path = choose_input_file()
        if not in_path:
            print("No input provided. Exiting.")
            sys.exit(1)

        if choice == "1":
            do_full_analysis(in_path)
        elif choice == "2":
            do_wide_one_syllable(in_path)

    except Exception as e:
        print(f"ERROR: {e}")
        press_enter("\nPress Enter to exit...")
        sys.exit(2)

if __name__ == "__main__":
    main()
