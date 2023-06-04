import csv
from datetime import datetime, timedelta
from collections import defaultdict
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

parse_csv('input.csv', 'output.csv')

input("Press any key to close script...")
