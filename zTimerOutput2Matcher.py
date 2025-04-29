import os
import csv

def list_csv_files():
    files = [f for f in os.listdir() if f.endswith('.csv')]
    print("Available CSV files:")
    for idx, file in enumerate(files):
        print(f"{idx + 1}. {file}")
    return files

def select_csv_file(files):
    choice = input("Enter the number of the file you want to process: ")
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(files):
            return files[idx]
        else:
            print("Invalid selection.")
            exit()
    except ValueError:
        print("Invalid input. Please enter a number.")
        exit()

def clean_and_split_csv(filename, rat1_id, rat2_id):
    base_name = os.path.splitext(filename)[0]
    with open(filename, 'r', newline='', encoding='utf-8') as infile:
        reader = csv.reader(infile)
        rows = list(reader)

    header = rows[0]
    cleaned_rows = [header]
    for row in rows[1:]:
        if row != header:
            cleaned_rows.append(row)

    # Categories
    categories = {
        "KEYA": [],
        "KEYS": [],
        "KEYD": [],
        "KEYW": [],
        "KEYJ": [],
        "KEYK": [],
        "KEYL": [],
        "KEYI": [],
        "Seize1": [],
        "Seize2": []
    }

    seizure_events = 0
    non_seizure_events = 0

    # Separate rows into two groups for chronology checking
    rat1_rows = []
    rat2_rows = []

    for row in cleaned_rows[1:]:
        key = row[4].upper().strip()
        seizure_label = row[6].strip().lower() if len(row) > 6 and row[6] else ""

        short_row = [row[0], row[1], row[2], row[3], row[4], row[5]]

        if key in ["A", "S", "D", "W"]:
            rat1_rows.append(row)
        elif key in ["J", "K", "L", "I"]:
            rat2_rows.append(row)

        if key == "A":
            categories["KEYA"].append(short_row)
        elif key == "S":
            categories["KEYS"].append(short_row)
        elif key == "D":
            categories["KEYD"].append(short_row)
        elif key == "W":
            if "seizure event" not in seizure_label:
                categories["KEYW"].append(short_row)
                non_seizure_events += 1
            else:
                categories["Seize1"].append(short_row)
                seizure_events += 1
        elif key == "J":
            categories["KEYJ"].append(short_row)
        elif key == "K":
            categories["KEYK"].append(short_row)
        elif key == "L":
            categories["KEYL"].append(short_row)
        elif key == "I":
            if "seizure event" not in seizure_label:
                categories["KEYI"].append(short_row)
                non_seizure_events += 1
            else:
                categories["Seize2"].append(short_row)
                seizure_events += 1

    # Chronology errors checking (separately for RAT1 and RAT2)
    chronology_errors = []

    def check_chronology(subset_rows, rat_label):
        errors = []
        for i in range(len(subset_rows) - 1):
            try:
                current_start = float(subset_rows[i][0])
                next_start = float(subset_rows[i + 1][0])
                current_end = float(subset_rows[i][1])
                next_end = float(subset_rows[i + 1][1])
                if next_start < current_start or next_end < current_end:
                    errors.append((rat_label, i + 1, subset_rows[i], subset_rows[i + 1]))
            except ValueError:
                continue
        return errors

    chronology_errors.extend(check_chronology(rat1_rows, rat1_id))
    chronology_errors.extend(check_chronology(rat2_rows, rat2_id))

    # Write output files
    output_stats = {}
    output_header = ['StartTime', 'EndTime', 'Dur', 'EventGlobal', 'Key', 'Label']

    for category, rows_list in categories.items():
        # Decide which rat ID to prepend
        if category in ["KEYA", "KEYS", "KEYD", "KEYW", "Seize1"]:
            rat_prefix = rat1_id
        elif category in ["KEYJ", "KEYK", "KEYL", "KEYI", "Seize2"]:
            rat_prefix = rat2_id
        else:
            rat_prefix = ""

        output_filename = f"{rat_prefix}_{base_name}_{category}.csv"
        with open(output_filename, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.writer(outfile)
            writer.writerow(output_header)
            writer.writerows(rows_list)
        output_stats[output_filename] = len(rows_list)

    # First, Print Chronology Errors
    print("\n=== Chronology Error Check ===")
    if chronology_errors:
        print(f"⚠️ Chronology Errors Detected ({len(chronology_errors)} cases):")
        for rat_label, idx, before, after in chronology_errors:
            print(f"  {rat_label} - Line {idx}:")
            print(f"    Before: {before}")
            print(f"    After:  {after}")
    else:
        print("No chronology errors detected.")

    # Then, Print Extraction Report
    print("\n=== Extraction Report ===")
    print(f"Processed file: {filename}")
    print("\nGenerated files and event counts:")
    for file, count in output_stats.items():
        print(f"  {file}: {count} events")

    print(f"\nTotal seizure events detected: {seizure_events}")
    print(f"Total non-seizure twitch events: {non_seizure_events}")

    input("\nPress Enter to exit...")

def main():
    files = list_csv_files()
    selected_file = select_csv_file(files)
    print("\nPlease enter the IDs for the two animals:")
    rat1_id = input("Enter ID for RAT1 (example: RAT1): ").strip()
    rat2_id = input("Enter ID for RAT2 (example: RAT2): ").strip()
    clean_and_split_csv(selected_file, rat1_id, rat2_id)

if __name__ == "__main__":
    main()
