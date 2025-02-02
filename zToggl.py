import csv
from datetime import datetime, timedelta, time as datetime_time
from collections import defaultdict
import operator
from functools import reduce
from collections import Counter
import time

# Helper function to parse time.
def parse_time(time_str):
    return datetime.strptime(time_str, '%H:%M:%S').time()

# Helper function to parse date.
def parse_date(date_str):
    return datetime.strptime(date_str, '%Y-%m-%d').date()

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


def report_hours_by_client_over_time(input_file, output_file):
    with open(input_file, 'r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        data = defaultdict(lambda: defaultdict(list))
        dates = set()
        
        for row in csv_reader:
            if row['Project'] == 'IVS':
                start_date = parse_date(row['Start date'])
                start_time = parse_time(row['Start time'])
                end_time = parse_time(row['End time'])
                
                start_datetime = datetime.combine(start_date, start_time)
                end_datetime = datetime.combine(start_date, end_time)
                
                if end_datetime < start_datetime:
                    end_datetime += timedelta(days=1)
                
                duration = end_datetime - start_datetime

                description_parts = row['Description'].split(' - ')
                
                if len(description_parts) >= 2:
                    client = description_parts[0]
                    category = description_parts[1]
                    study = description_parts[2] if len(description_parts) > 2 else "N/A"
                    
                    entry_key = f"{client} - {category}"
                    if category.lower() == "study" and study != "N/A":
                        entry_key += f" - {study}"
                    
                    data[start_date][entry_key].append((start_datetime, end_datetime, duration))
                    dates.add(start_date)

    sorted_dates = sorted(dates)
    
    # Create the date range for the new filename
    if sorted_dates:
        start_date_str = sorted_dates[0].strftime('%Y-%m-%d')
        end_date_str = sorted_dates[-1].strftime('%Y-%m-%d')
        new_output_file = f"{start_date_str}-{end_date_str}-function5output.csv"
    else:
        new_output_file = "no-dates-function5output.csv"

    # Original output file
    with open(output_file, 'w', newline='') as out_file:
        csv_writer = csv.writer(out_file)
        csv_writer.writerow(['Date', 'Client/Category/Study', 'Hours', 'Percentage', 'Suggested Time Window'])

        # New output file
        with open(new_output_file, 'w', newline='') as new_out_file:
            new_csv_writer = csv.writer(new_out_file)
            new_csv_writer.writerow(['YYYYMMDD', 'Client/Category/Study', 'Hours', 'Percentage', 'TotalOfDay'])

            print("\n--- Hours by Client, Category, and Study over Time ---")
            
            for date in sorted_dates:
                print(f"\nDate: {date.strftime('%Y-%m-%d')}")
                print("-" * 60)
                
                total_duration = timedelta()
                earliest_start_after_6am = None
                
                for entry_data in data[date].values():
                    for start, end, duration in entry_data:
                        total_duration += duration
                        if start.time() >= datetime_time(6, 0):
                            if earliest_start_after_6am is None or start < earliest_start_after_6am:
                                earliest_start_after_6am = start
                
                if earliest_start_after_6am is None:
                    earliest_start_after_6am = datetime.combine(date, datetime_time(6, 0))
                
                sorted_entries = sorted(data[date].items(), key=lambda x: reduce(operator.add, (duration for _, _, duration in x[1]), timedelta()), reverse=True)
                
                # Calculate total hours for the day
                total_hours = total_duration.total_seconds() / 3600
                
                for entry, entry_data in sorted_entries:
                    total_entry_duration = reduce(operator.add, (duration for _, _, duration in entry_data), timedelta())
                    hours = total_entry_duration.total_seconds() / 3600
                    percentage = (total_entry_duration / total_duration) * 100 if total_duration else 0
                    
                    entry_start = min(start for start, _, _ in entry_data)
                    if entry_start.time() < datetime_time(6, 0):
                        entry_start = earliest_start_after_6am
                    suggested_end = entry_start + total_entry_duration
                    time_window_str = f"{entry_start.strftime('%H:%M')}-{suggested_end.strftime('%H:%M')}"
                    
                    print(f"{entry.ljust(30)}: {hours:.2f} hours ({percentage:.2f}%) - {time_window_str}")
                    
                    # Write to original output file
                    csv_writer.writerow([date.strftime('%Y-%m-%d'), entry, f"{hours:.2f}", f"{percentage:.2f}", time_window_str])
                    
                    # Write to new output file
                    new_csv_writer.writerow([date.strftime('%Y%m%d'), entry, f"{hours:.2f}", f"{percentage:.2f}", f"{total_hours:.2f}"])
                
                suggested_end_total = earliest_start_after_6am + total_duration
                total_time_window = f"{earliest_start_after_6am.strftime('%H:%M')}-{suggested_end_total.strftime('%H:%M')}"
                
                print("-" * 60)
                print(f"{'Total'.ljust(30)}: {total_hours:.2f} hours - {total_time_window}")
                
                csv_writer.writerow([date.strftime('%Y-%m-%d'), 'Total', f"{total_hours:.2f}", "100.00", total_time_window])
                csv_writer.writerow([])  # Empty row for readability

    print(f"\nOriginal report has been written to {output_file}")
    print(f"Additional report has been written to {new_output_file}")


def report_metelao_instances(input_file):
    with open(input_file, 'r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        metelao_instances = []
        
        for row in csv_reader:
            if 'metelao' in row['Description'].lower():
                start_date = parse_date(row['Start date'])
                start_time = parse_time(row['Start time'])
                end_time = parse_time(row['End time'])
                
                start_datetime = datetime.combine(start_date, start_time)
                end_datetime = datetime.combine(start_date, end_time)
                
                if end_datetime < start_datetime:
                    end_datetime += timedelta(days=1)
                
                metelao_instances.append((start_datetime, end_datetime))

    if metelao_instances:
        print("\n--- Metelao Instances ---")
        for start, end in sorted(metelao_instances):
            print(f"Date: {start.strftime('%Y-%m-%d')}, Time window: {start.strftime('%H:%M')} - {end.strftime('%H:%M')}")
        
        print(f"\nTotal instances of 'metelao': {len(metelao_instances)}")
    else:
        print("\nNo instances of 'metelao' found in the document.")



def main():
    print("Choose an option:")
    print("1. Parse CSV file")
    print("2. Tally hours from CSV file")
    print("3. Update file with 15 most common descriptions")
    print("4. Report hours by Client or Category for projects")
    print("5. Report hours by Client over time for projects")
    print("6. Report instances of 'metelao'")
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

    elif choice == '4':
        input_file = input("Enter the name of the input CSV file: ")
        # If no input file is provided, use a default name.
        if not input_file.strip():
            input_file = "input_zT.csv"
        
        report_hours_by_client_category(input_file)
    
    elif choice == '5':
        input_file = input("Enter the name of the input CSV file: ")
        output_file = input("Enter the name of the output CSV file: ")

        # If no input file is provided, use a default name.
        if not input_file.strip():
            input_file = "input_zT.csv"
        
        # If no output file is provided, use a default name.
        if not output_file.strip():
            output_file = "client_hours_report.csv"
        
        report_hours_by_client_over_time(input_file, output_file)

    elif choice == '6':
        input_file = input("Enter the name of the input CSV file: ")

        # If no input file is provided, use a default name.
        if not input_file.strip():
            input_file = "input_zT.csv"
        
        report_metelao_instances(input_file)


    # Handle other choices here...

    input("Press any key to close script...")

# This line ensures that main() gets called when this script is run directly.
if __name__ == "__main__":
    main()