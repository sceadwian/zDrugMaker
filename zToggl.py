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
        for row in csv_reader:
            if row['Project'] == 'IVS':
                data[row['Start date']].append((parse_time(row['Start time']), parse_time(row['End time'])))

        with open(output_file, 'w', newline='') as out_file:
            csv_writer = csv.writer(out_file)
            csv_writer.writerow(['Date', 'Start time', 'End time', 'Total hours'])
            for date, time_ranges in data.items():
                min_start_time = min(time_ranges, key=lambda x: x[0])[0]
                max_end_time = max(time_ranges, key=lambda x: x[1])[1]
                total_hours = sum((end_time - start_time).total_seconds() / 3600 for start_time, end_time in time_ranges)
                csv_writer.writerow([date, min_start_time.time(), max_end_time.time(), total_hours])
                print(f'Date: {date}, Start time: {min_start_time.time()}, End time: {max_end_time.time()}, Total hours: {total_hours}')

parse_csv('input.csv', 'output.csv')
