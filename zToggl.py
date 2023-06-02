import csv
from datetime import datetime, timedelta
from collections import defaultdict

def parse_time(time_str):
    return datetime.strptime(time_str, '%H:%M:%S')

def parse_date(date_str):
    return datetime.strptime(date_str, '%Y-%m-%d')

def parse_csv(input_file, output_file):
    with open(input_file, 'r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        data = defaultdict(list)
        description_data = defaultdict(lambda: defaultdict(timedelta))
        for row in csv_reader:
            if row['Project'] == 'IVS':
                start_time = parse_time(row['Start time'])
                end_time = parse_time(row['End time'])
                if end_time < start_time:
                    end_time += timedelta(days=1)
                duration = end_time - start_time
                data[row['Start date']].append((start_time, end_time))
                if row['Description']:
                    parts = row['Description'].split(' - ')
                    if len(parts) == 3:
                        client, bill, study = parts
                    elif len(parts) == 2:
                        client, bill = parts
                        study = 'N/A'
                    else:
                        continue
                    description_data[row['Start date']][(client, bill, study)] += duration

        with open(output_file, 'w', newline='') as out_file:
            csv_writer = csv.writer(out_file)
            csv_writer.writerow(['Date', 'Start time', 'End time', 'Total hours'])
            for date, time_ranges in data.items():
                time_ranges.sort(key=lambda x: x[0])
                start_time, end_time = time_ranges[0]
                for next_start_time, next_end_time in time_ranges[1:]:
                    if next_start_time - end_time > timedelta(hours=1):
                        total_hours = (end_time - start_time).total_seconds() / 3600
                        csv_writer.writerow([date, start_time.time(), end_time.time(), f'{total_hours:.2f}'])
                        print(f'Date: {date}, Start time: {start_time.time()}, End time: {end_time.time()}, Total hours: {total_hours:.2f}')
                        start_time = next_start_time
                    end_time = max(end_time, next_end_time)
                total_hours = (end_time - start_time).total_seconds() / 3600
                csv_writer.writerow([date, start_time.time(), end_time.time(), f'{total_hours:.2f}'])
                print(f'Date: {date}, Start time: {start_time.time()}, End time: {end_time.time()}, Total hours: {total_hours:.2f}')
                print("Description breakdown:")
                for (client, bill, study), duration in description_data[date].items():
                    task_hours = duration.total_seconds() / 3600
                    print(f'\033[93mClient:\033[0m {client}, \033[93mBill:\033[0m {bill}, \033[93mStudy:\033[0m {study}: \033[92m{task_hours:.2f} hours\033[0m')
                print('-' * 40)

parse_csv('input.csv', 'output.csv')
