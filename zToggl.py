import csv
from datetime import datetime, timedelta
from collections import defaultdict
from collections import Counter
import time

# Helper function to parse time.
def parse_time(time_str):
    return datetime.strptime(time_str, '%H:%M:%S')

# Helper function to parse date.
def parse_date(date_str):
    return datetime.strptime(date_str, '%Y-%m-%d')

# Main function to parse the CSV and generate a summary.
def parse_csv(input_file, output_file):
    with open(input_file, 'r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        
        # Use defaultdicts to store the data.
        data = defaultdict(list)
        description_data = defaultdict(lambda: defaultdict(timedelta))
        overall_description_data = defaultdict(timedelta)
        
        # Iterate over each row.
        for row in csv_reader:
            if row['Project'] == 'IVS':
                start_time = parse_time(row['Start time'])
                end_time = parse_time(row['End time'])
                
                # Handle cases where end_time is earlier than start_time.
                if end_time < start_time:
                    end_time += timedelta(days=1)
                    
                # Calculate duration.
                duration = end_time - start_time
                
                # Append time range to data.
                data[row['Start date']].append((start_time, end_time))
                
                # Split and process the description.
                if row['Description']:
                    parts = row['Description'].split(' - ')
                    
                    # Handle cases with different number of parts.
                    if len(parts) == 3:
                        client, bill, study = parts
                    elif len(parts) == 2:
                        client, bill = parts
                        study = 'N/A'
                    else:
                        continue
                        
                    # Update description data.
                    description_data[row['Start date']][(client, bill, study)] += duration
                    overall_description_data[(client, bill, study)] += duration

        # Write results to output CSV.
        with open(output_file, 'w', newline='') as out_file:
            csv_writer = csv.writer(out_file)
            csv_writer.writerow(['Date', 'Start time', 'End time', 'Total hours'])
            
            # Iterate over the data sorted by date.
            for date, time_ranges in sorted(data.items()):
                time_ranges.sort(key=lambda x: x[0])
                
                start_time, end_time = time_ranges[0]
                
                # Merge overlapping time ranges and calculate total hours.
                for next_start_time, next_end_time in time_ranges[1:]:
                    if next_start_time - end_time > timedelta(hours=1):
                        total_hours = (end_time - start_time).total_seconds() / 3600
                        csv_writer.writerow([date, start_time.time(), end_time.time(), f'{total_hours:.2f}'])
                        start_time = next_start_time
                    end_time = max(end_time, next_end_time)
                
                # Calculate total hours for the last time range.
                total_hours = (end_time - start_time).total_seconds() / 3600
                csv_writer.writerow([date, start_time.time(), end_time.time(), f'{total_hours:.2f}'])
                
                # Print breakdown by description.
                print("Description breakdown:")
                for (client, bill, study), duration in sorted(description_data[date].items()):
                    task_hours = duration.total_seconds() / 3600
                    print(f'\033[93mClient:\033[0m {client}, \033[93mBill:\033[0m {bill}, \033[93mStudy:\033[0m {study}: \033[92m{task_hours:.2f} hours\033[0m')
                print('-' * 40)
                time.sleep(0.4)
            
            # Write overall description breakdown.
            csv_writer.writerow(['Overall Description Breakdown'])
            for (client, bill, study), duration in sorted(overall_description_data.items(), key=lambda x: x[0][0]):
                total_hours = duration.total_seconds() / 3600
                csv_writer.writerow([f'Client: {client}, Bill: {bill}, Study: {study}', f'{total_hours:.2f} hours'])


def tally_hours(input_file):
    with open(input_file, 'r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        hours_data = defaultdict(timedelta)
        description_data = defaultdict(timedelta)

        # Total time across all tasks.
        total_time = timedelta()
        
        for row in csv_reader:
            start_time = parse_time(row['Start time'])
            end_time = parse_time(row['End time'])
            
            if end_time < start_time:
                end_time += timedelta(days=1)
            
            duration = end_time - start_time
            project_task = (row['Project'], row['Task'])
            hours_data[project_task] += duration
            
            # Only include non-'IVS' entries in the description tally.
            if row['Project'] != 'IVS':
                description_data[row['Description']] += duration
            
            total_time += duration

        # Convert total_time to seconds for easy calculation of percentage.
        total_seconds = total_time.total_seconds()
        
        # Sort the results by total hours and print them.
        print('--- Project & Task Tally ---')
        sorted_results = sorted(hours_data.items(), key=lambda x: x[1], reverse=True)
        for (project, task), duration in sorted_results:
            task_seconds = duration.total_seconds()
            total_hours = task_seconds / 3600
            percentage = (task_seconds / total_seconds) * 100
            print(f'\033[93mProject:\033[0m {project}, \033[93mTask:\033[0m {task}: \033[92m{total_hours:.2f} hours ({percentage:.2f}%)\033[0m')
        
        # Sort and print the results by descriptions.
        print('\n--- Description Tally ---')
        sorted_descriptions = sorted(description_data.items(), key=lambda x: x[1], reverse=True)
        for description, duration in sorted_descriptions:
            task_seconds = duration.total_seconds()
            total_hours = task_seconds / 3600
            percentage = (task_seconds / total_seconds) * 100
            print(f'\033[93mDescription:\033[0m {description}: \033[92m{total_hours:.2f} hours ({percentage:.2f}%)\033[0m')

def common_tasks(input_file, output_file):
    with open(input_file, 'r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        description_counter = Counter()
        project_dict = {}

        for row in csv_reader:
            description = row['Description']
            description_counter[description] += 1
            if description not in project_dict:
                project_dict[description] = row['Project']

        most_common_descriptions = description_counter.most_common(15)

        existing_descriptions = set()

        try:
            with open(output_file, 'r') as out_file:
                csv_reader = csv.reader(out_file)
                for row in csv_reader:
                    existing_descriptions.add(row[0])
        except FileNotFoundError:
            pass

        with open(output_file, 'a', newline='') as out_file:
            csv_writer = csv.writer(out_file)
            for description, _ in most_common_descriptions:
                if description not in existing_descriptions:
                    csv_writer.writerow([f'{description} ({project_dict[description]})'])

def main():
    print("Choose an option:")
    print("1. Parse CSV file")
    print("2. Tally hours from CSV file")
    print("3. Update file with 15 most common descriptions")
    # Print other options here...
    
    choice = input("Your choice: ")
    
    if choice == '1':
        input_file = input("Enter the name of the input CSV file: ")
        output_file = input("Enter the name of the output CSV file: ")

        # If no input file is provided, use a default name.
        if not input_file.strip():
            input_file = "input_zT.csv"

        # If no output file is provided, use a default name.
        if not output_file.strip():
            output_file = "output_zT.csv"
        
        parse_csv(input_file, output_file)
        
    elif choice == '2':
        input_file = input("Enter the name of the input CSV file: ")

        # If no input file is provided, use a default name.
        if not input_file.strip():
            input_file = "input_zT.csv"
        
        tally_hours(input_file)

    elif choice == '3':
        input_file = input("Enter the name of the input CSV file: ")
        output_file = input("Enter the name of the output CSV file: ")

        # If no file names are provided, use default names.
        if not input_file.strip():
            input_file = "input_zT.csv"
        if not output_file.strip():
            output_file = "tasks_zT.csv"

        common_tasks(input_file, output_file)

    # Handle other choices here...

    input("Press any key to close script...")

# This line ensures that main() gets called when this script is run directly.
if __name__ == "__main__":
    main()