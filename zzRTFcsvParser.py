import csv
import os

def parse_rtf_file(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    # Remove empty lines and leading/trailing whitespace
    lines = [line.strip() for line in lines if line.strip()]

    # Find the index of the separator line
    separator_index = next(i for i, line in enumerate(lines) if len(line) == len(lines[0]))

    # Extract the headers from the line above the separator
    headers = lines[separator_index - 1].split('\t')

    # Extract the data rows below the separator
    data_rows = [line.split('\t') for line in lines[separator_index + 1:]]

    with open(output_file, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(headers)  # Write the headers to the CSV file

        for row in data_rows:
            writer.writerow(row)  # Write each data row to the CSV file

    print(f"CSV file '{output_file}' has been generated.")


# Get the current directory
current_dir = os.getcwd()

# Find all .rtf files in the current directory
rtf_files = [file for file in os.listdir(current_dir) if file.lower().endswith('.rtf')]

# Process each .rtf file
for rtf_file in rtf_files:
    input_file = os.path.join(current_dir, rtf_file)
    output_file = os.path.join(current_dir, f"{os.path.splitext(rtf_file)[0]}.csv")

    print(f"Processing file: {rtf_file}")
    parse_rtf_file(input_file, output_file)

# Provide a summary of the parsed data
print(f"\nSummary:\n")
for rtf_file in rtf_files:
    csv_file = f"{os.path.splitext(rtf_file)[0]}.csv"
    print(f"{rtf_file} -> {csv_file}")

# Ask the user to press any key to close the script
input("\nPress any key to close the script...")
