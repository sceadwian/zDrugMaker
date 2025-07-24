#!/usr/bin/env python3
from pathlib import Path
import json, sys, traceback, unicodedata

def expected_filename(data: dict) -> str:
    """Build the canonical 'Name Surname.json' string, stripped & normalised."""
    first  = unicodedata.normalize("NFC", data["Name"].strip())
    last   = unicodedata.normalize("NFC", data["Surname"].strip())
    return f"{first} {last}.json"

def find_mismatches(root: Path):
    """Return [(Path, expected_name)] for every JSON whose file name is wrong."""
    mismatches = []
    for fp in root.rglob("*.json"):                    # ① recurse
        try:
            with fp.open(encoding="utf-8") as f:
                data = json.load(f)

            expected = expected_filename(data)
            if fp.name.lower() != expected.lower():    # ② case-insensitive
                mismatches.append((fp, expected))

        except (KeyError, json.JSONDecodeError) as e:
            print(f"⚠️  Skipping {fp}: {e}")           # bad JSON or missing keys
    return mismatches

def rename_files(pairs):
    for old, expected in pairs:
        new_path = old.with_name(expected)
        if new_path.exists():
            print(f"❌  {expected} already exists — skipping")
            continue
        old.rename(new_path)
        print(f"✔️  {old.name}  ➜  {expected}")

def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    print(f"🔍 Scanning {root.resolve()} …")

    bad = find_mismatches(root)

    if not bad:
        print("✅ All JSON files appear to be named correctly.")
        return

    print("\nFiles that don’t match the Name/Surname inside:")
    for old, expected in bad:
        print(f"  {old.relative_to(root)}  ➜  {expected}")

    if input("\nRename these files now? [y/N] ").strip().lower() == "y":
        rename_files(bad)
    else:
        print("No changes made.")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()   # full error in case something unexpected happens
    finally:
        input("\nDone. Press Enter to close…")
