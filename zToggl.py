import csv
import os
import sys
import time
from datetime import datetime, timedelta, time as datetime_time
from collections import defaultdict, Counter

# ANSI colours.
YEL = '\033[93m'
GRN = '\033[92m'
CYN = '\033[96m'
RED = '\033[91m'
DIM = '\033[2m'
BLD = '\033[1m'
RST = '\033[0m'

# Folder the script lives in — CSVs are picked from and written to here.
FOLDER = os.path.dirname(os.path.abspath(__file__))

# Default output names, excluded from the input-file picker so the
# script's own products don't clutter the list.
KNOWN_OUTPUTS = {'output_zT.csv', 'tasks_zT.csv', 'client_hours_report.csv'}


# Helper function to parse time.
def parse_time(time_str):
    return datetime.strptime(time_str, '%H:%M:%S').time()


# Helper function to parse date.
def parse_date(date_str):
    return datetime.strptime(date_str, '%Y-%m-%d').date()


# Build full start/end datetimes for a row using both the Start date and
# End date columns, so entries that cross midnight are handled correctly.
def entry_times(row):
    start = datetime.combine(parse_date(row['Start date']), parse_time(row['Start time']))
    end = datetime.combine(parse_date(row['End date']), parse_time(row['End time']))
    if end < start:
        end += timedelta(days=1)
    return start, end, end - start


# Ask a yes/no question before printing any report to the screen.
def ask_yes_no(question, default=True):
    hint = 'Y/n' if default else 'y/N'
    answer = input(f'{CYN}{question}{RST} [{hint}]: ').strip().lower()
    if not answer:
        return default
    return answer in ('y', 'yes')


# List the CSV files in the script's folder and let the user pick one by
# number instead of typing the filename out. With allow_all=True an extra
# 'a' option returns every listed file, for reports spanning several months.
def choose_input_csv(allow_all=False):
    csvs = sorted(
        f for f in os.listdir(FOLDER)
        if f.lower().endswith('.csv')
        and f not in KNOWN_OUTPUTS
        and 'function5output' not in f
    )

    if not csvs:
        print(f'{RED}No CSV files found in {FOLDER}.{RST}')
        name = input('Enter a CSV filename manually: ').strip()
        return os.path.join(FOLDER, name) if name else None

    print(f'\n{BLD}Available CSV files:{RST}')
    for i, name in enumerate(csvs, 1):
        print(f'  {YEL}{i:>2}{RST}. {name}')
    if allow_all:
        print(f'  {YEL} a{RST}. ALL of the files above (combined report)')
    print(f'  {YEL} 0{RST}. Type a filename manually')

    while True:
        choice = input(f'{CYN}Pick a file{RST} [1-{len(csvs)}]: ').strip().lower()
        if allow_all and choice == 'a':
            print(f'{GRN}Selected all {len(csvs)} files.{RST}')
            return [os.path.join(FOLDER, name) for name in csvs]
        if choice == '0':
            name = input('Enter a CSV filename: ').strip()
            return os.path.join(FOLDER, name) if name else None
        if choice.isdigit() and 1 <= int(choice) <= len(csvs):
            picked = csvs[int(choice) - 1]
            print(f'{GRN}Selected file: {BLD}{picked}{RST}')
            return os.path.join(FOLDER, picked)
        print(f'{RED}Not a valid choice, try again.{RST}')


# List the projects found in the chosen CSV (with entry counts) and let
# the user pick which one to analyze. Defaults to IVS when present.
def choose_project(input_file):
    with open(input_file, 'r') as csv_file:
        counts = Counter(row['Project'] for row in csv.DictReader(csv_file) if row['Project'])

    if not counts:
        print(f'{RED}No projects found in this file.{RST}')
        return None

    projects = [name for name, _ in counts.most_common()]
    default = 'IVS' if 'IVS' in counts else projects[0]

    # Put the default first so option 1 and Enter mean the same thing.
    projects.remove(default)
    projects.insert(0, default)

    print(f'\n{BLD}Projects in this file:{RST}')
    for i, name in enumerate(projects, 1):
        marker = f' {DIM}(default){RST}' if name == default else ''
        print(f'  {YEL}{i:>2}{RST}. {name} {DIM}({counts[name]} entries){RST}{marker}')

    while True:
        choice = input(f'{CYN}Pick a project{RST} [Enter = {default}]: ').strip()
        if not choice:
            picked = default
        elif choice.isdigit() and 1 <= int(choice) <= len(projects):
            picked = projects[int(choice) - 1]
        else:
            print(f'{RED}Not a valid choice, try again.{RST}')
            continue
        print(f'{GRN}Selected project: {BLD}{picked}{RST}')
        return picked


# Prompt for an output filename with a default.
def choose_output_file(default):
    name = input(f'{CYN}Output filename{RST} [default: {default}]: ').strip()
    return os.path.join(FOLDER, name if name else default)


# Option 1: merge a project's time ranges per day and write a summary CSV.
def parse_csv(input_file, output_file, project):
    data = defaultdict(list)
    description_data = defaultdict(lambda: defaultdict(timedelta))
    overall_description_data = defaultdict(timedelta)

    with open(input_file, 'r') as csv_file:
        for row in csv.DictReader(csv_file):
            if row['Project'] != project:
                continue

            start, end, duration = entry_times(row)
            data[row['Start date']].append((start, end))

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
                overall_description_data[(client, bill, study)] += duration

    if not data:
        print(f'{RED}No "{project}" entries found in this file — nothing to write.{RST}')
        return

    show_breakdown = ask_yes_no('Print daily description breakdowns to screen?')

    with open(output_file, 'w', newline='') as out_file:
        csv_writer = csv.writer(out_file)
        csv_writer.writerow(['Date', 'Start time', 'End time', 'Total hours'])

        for date, time_ranges in sorted(data.items()):
            time_ranges.sort(key=lambda x: x[0])
            start, end = time_ranges[0]

            # Merge time ranges separated by less than an hour.
            for next_start, next_end in time_ranges[1:]:
                if next_start - end > timedelta(hours=1):
                    total_hours = (end - start).total_seconds() / 3600
                    csv_writer.writerow([date, start.time(), end.time(), f'{total_hours:.2f}'])
                    start = next_start
                end = max(end, next_end)

            total_hours = (end - start).total_seconds() / 3600
            csv_writer.writerow([date, start.time(), end.time(), f'{total_hours:.2f}'])

            if show_breakdown:
                print(f'\n{BLD}{date}{RST} — description breakdown:')
                for (client, bill, study), duration in sorted(description_data[date].items()):
                    task_hours = duration.total_seconds() / 3600
                    print(f'{YEL}Client:{RST} {client}, {YEL}Bill:{RST} {bill}, '
                          f'{YEL}Study:{RST} {study}: {GRN}{task_hours:.2f} hours{RST}')
                print(DIM + '-' * 40 + RST)
                time.sleep(0.4)

        csv_writer.writerow(['Overall Description Breakdown'])
        for (client, bill, study), duration in sorted(overall_description_data.items(), key=lambda x: x[0][0]):
            total_hours = duration.total_seconds() / 3600
            csv_writer.writerow([f'Client: {client}, Bill: {bill}, Study: {study}', f'{total_hours:.2f} hours'])

    print(f'{GRN}Summary written to {output_file}{RST}')


# Option 2: tally hours per project/task and per description.
def tally_hours(input_file):
    hours_data = defaultdict(timedelta)
    description_data = defaultdict(timedelta)
    total_time = timedelta()

    with open(input_file, 'r') as csv_file:
        for row in csv.DictReader(csv_file):
            _, _, duration = entry_times(row)
            hours_data[(row['Project'], row['Task'])] += duration

            # Only include non-'IVS' entries in the description tally.
            if row['Project'] != 'IVS':
                description_data[row['Description']] += duration

            total_time += duration

    total_seconds = total_time.total_seconds()

    if ask_yes_no('Print project & task tally to screen?'):
        print(f'\n{BLD}--- Project & Task Tally ---{RST}')
        for (project, task), duration in sorted(hours_data.items(), key=lambda x: x[1], reverse=True):
            task_seconds = duration.total_seconds()
            total_hours = task_seconds / 3600
            percentage = (task_seconds / total_seconds) * 100
            print(f'{YEL}Project:{RST} {project}, {YEL}Task:{RST} {task}: '
                  f'{GRN}{total_hours:.2f} hours ({percentage:.2f}%){RST}')

    if ask_yes_no('Print description tally to screen?'):
        print(f'\n{BLD}--- Description Tally ---{RST}')
        for description, duration in sorted(description_data.items(), key=lambda x: x[1], reverse=True):
            task_seconds = duration.total_seconds()
            total_hours = task_seconds / 3600
            percentage = (task_seconds / total_seconds) * 100
            print(f'{YEL}Description:{RST} {description}: '
                  f'{GRN}{total_hours:.2f} hours ({percentage:.2f}%){RST}')


# Option 3: append the 15 most common descriptions to a tasks file.
def common_tasks(input_file, output_file):
    description_counter = Counter()
    project_dict = {}

    with open(input_file, 'r') as csv_file:
        for row in csv.DictReader(csv_file):
            description = row['Description']
            description_counter[description] += 1
            if description not in project_dict:
                project_dict[description] = row['Project']

    most_common_descriptions = description_counter.most_common(15)

    existing_descriptions = set()
    try:
        with open(output_file, 'r') as out_file:
            for row in csv.reader(out_file):
                existing_descriptions.add(row[0])
    except FileNotFoundError:
        pass

    added = []
    with open(output_file, 'a', newline='') as out_file:
        csv_writer = csv.writer(out_file)
        for description, _ in most_common_descriptions:
            entry = f'{description} ({project_dict[description]})'
            if entry not in existing_descriptions:
                csv_writer.writerow([entry])
                added.append(entry)

    print(f'{GRN}{len(added)} new description(s) added to {output_file}{RST}')
    if added and ask_yes_no('Print the newly added descriptions to screen?'):
        for entry in added:
            print(f'  {entry}')


# Option 4: tally a project's hours by client and by category.
def report_hours_by_client_category(input_file, project):
    client_hours = defaultdict(timedelta)
    category_hours = defaultdict(timedelta)
    total_time = timedelta()

    with open(input_file, 'r') as csv_file:
        for row in csv.DictReader(csv_file):
            if row['Project'] != project:
                continue
            parts = row['Description'].split(' - ')
            if len(parts) < 2:
                continue
            _, _, duration = entry_times(row)
            client_hours[parts[0]] += duration
            category_hours[parts[1]] += duration
            total_time += duration

    if not total_time:
        print(f'{RED}No "{project}" entries with a "Client - Category" description found.{RST}')
        return

    total_seconds = total_time.total_seconds()

    if ask_yes_no('Print hours by client to screen?'):
        print(f'\n{BLD}--- {project} Hours by Client ---{RST}')
        for client, duration in sorted(client_hours.items(), key=lambda x: x[1], reverse=True):
            hours = duration.total_seconds() / 3600
            percentage = (duration.total_seconds() / total_seconds) * 100
            print(f'{YEL}{client.ljust(25)}{RST}: {GRN}{hours:.2f} hours ({percentage:.2f}%){RST}')

    if ask_yes_no('Print hours by category to screen?'):
        print(f'\n{BLD}--- {project} Hours by Category ---{RST}')
        for category, duration in sorted(category_hours.items(), key=lambda x: x[1], reverse=True):
            hours = duration.total_seconds() / 3600
            percentage = (duration.total_seconds() / total_seconds) * 100
            print(f'{YEL}{category.ljust(25)}{RST}: {GRN}{hours:.2f} hours ({percentage:.2f}%){RST}')

    total_hours = total_seconds / 3600
    print(f'\n{BLD}Total {project} time:{RST} {GRN}{total_hours:.2f} hours{RST}')


# Option 5: report a project's hours by client/category/study over time.
def report_hours_by_client_over_time(input_file, output_file, project):
    data = defaultdict(lambda: defaultdict(list))
    dates = set()

    with open(input_file, 'r') as csv_file:
        for row in csv.DictReader(csv_file):
            if row['Project'] != project:
                continue

            start, end, duration = entry_times(row)
            start_date = start.date()

            description_parts = row['Description'].split(' - ')
            if len(description_parts) < 2:
                continue

            client = description_parts[0]
            category = description_parts[1]
            study = description_parts[2] if len(description_parts) > 2 else 'N/A'

            entry_key = f'{client} - {category}'
            if category.lower() == 'study' and study != 'N/A':
                entry_key += f' - {study}'

            data[start_date][entry_key].append((start, end, duration))
            dates.add(start_date)

    if not dates:
        print(f'{RED}No "{project}" entries with a "Client - Category" description found — nothing to write.{RST}')
        return

    sorted_dates = sorted(dates)

    # Create the date range for the second output filename.
    start_date_str = sorted_dates[0].strftime('%Y-%m-%d')
    end_date_str = sorted_dates[-1].strftime('%Y-%m-%d')
    new_output_file = os.path.join(FOLDER, f'{start_date_str}-{end_date_str}-function5output.csv')

    show_report = ask_yes_no('Print the day-by-day report to screen?')

    with open(output_file, 'w', newline='') as out_file, \
         open(new_output_file, 'w', newline='') as new_out_file:
        csv_writer = csv.writer(out_file)
        csv_writer.writerow(['Date', 'Client/Category/Study', 'Hours', 'Percentage', 'Suggested Time Window'])

        new_csv_writer = csv.writer(new_out_file)
        new_csv_writer.writerow(['YYYYMMDD', 'Client/Category/Study', 'Hours', 'Percentage', 'TotalOfDay'])

        if show_report:
            print(f'\n{BLD}--- {project} Hours by Client, Category, and Study over Time ---{RST}')

        for date in sorted_dates:
            if show_report:
                print(f'\n{BLD}Date: {date.strftime("%Y-%m-%d")}{RST}')
                print(DIM + '-' * 60 + RST)

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

            sorted_entries = sorted(
                data[date].items(),
                key=lambda x: sum((duration for _, _, duration in x[1]), timedelta()),
                reverse=True,
            )

            total_hours = total_duration.total_seconds() / 3600

            for entry, entry_data in sorted_entries:
                total_entry_duration = sum((duration for _, _, duration in entry_data), timedelta())
                hours = total_entry_duration.total_seconds() / 3600
                percentage = (total_entry_duration / total_duration) * 100 if total_duration else 0

                entry_start = min(start for start, _, _ in entry_data)
                if entry_start.time() < datetime_time(6, 0):
                    entry_start = earliest_start_after_6am
                suggested_end = entry_start + total_entry_duration
                time_window_str = f'{entry_start.strftime("%H:%M")}-{suggested_end.strftime("%H:%M")}'

                if show_report:
                    print(f'{entry.ljust(30)}: {GRN}{hours:.2f} hours ({percentage:.2f}%){RST} - {time_window_str}')

                csv_writer.writerow([date.strftime('%Y-%m-%d'), entry, f'{hours:.2f}', f'{percentage:.2f}', time_window_str])
                new_csv_writer.writerow([date.strftime('%Y%m%d'), entry, f'{hours:.2f}', f'{percentage:.2f}', f'{total_hours:.2f}'])

            suggested_end_total = earliest_start_after_6am + total_duration
            total_time_window = f'{earliest_start_after_6am.strftime("%H:%M")}-{suggested_end_total.strftime("%H:%M")}'

            if show_report:
                print(DIM + '-' * 60 + RST)
                print(f'{"Total".ljust(30)}: {GRN}{total_hours:.2f} hours{RST} - {total_time_window}')

            csv_writer.writerow([date.strftime('%Y-%m-%d'), 'Total', f'{total_hours:.2f}', '100.00', total_time_window])
            csv_writer.writerow([])  # Empty row for readability.

    print(f'\n{GRN}Original report has been written to {output_file}{RST}')
    print(f'{GRN}Additional report has been written to {new_output_file}{RST}')


# Option 6: analyze a recurring event (Metelao, Direitinha, Fernando, ...)
# across one or several CSV files.

# Show the most common recurring descriptions across the chosen files and
# let the user pick which one to analyze. Defaults to Metelao when present.
def choose_search_term(input_files):
    counter = Counter()
    for path in input_files:
        with open(path, 'r') as csv_file:
            for row in csv.DictReader(csv_file):
                description = row['Description'].strip()
                if description:
                    counter[description] += 1

    if not counter:
        print(f'{RED}No descriptions found in the chosen file(s).{RST}')
        return None

    candidates = [d for d, _ in counter.most_common(12)]

    # Metelao is the traditional default — pull it into the list if needed.
    default = next((d for d in candidates if 'metelao' in d.lower()), None)
    if default is None:
        default = next((d for d in counter if 'metelao' in d.lower()), None)
        if default:
            candidates.append(default)
    if default is None:
        default = candidates[0]
    candidates.remove(default)
    candidates.insert(0, default)

    print(f'\n{BLD}Most common recurring events in the chosen file(s):{RST}')
    for i, name in enumerate(candidates, 1):
        marker = f' {DIM}(default){RST}' if name == default else ''
        print(f'  {YEL}{i:>2}{RST}. {name} {DIM}({counter[name]}×){RST}{marker}')
    print(f'  {YEL} 0{RST}. Type a search term manually')

    while True:
        choice = input(f'{CYN}Pick an event{RST} [Enter = {default}]: ').strip()
        if not choice:
            picked = default
        elif choice == '0':
            picked = input('Enter search text (matched anywhere in the description): ').strip()
            if not picked:
                print(f'{RED}Nothing entered, try again.{RST}')
                continue
        elif choice.isdigit() and 1 <= int(choice) <= len(candidates):
            picked = candidates[int(choice) - 1]
        else:
            print(f'{RED}Not a valid choice, try again.{RST}')
            continue
        print(f'{GRN}Selected event: {BLD}{picked}{RST}')
        return picked


# Collect every matching entry (case-insensitive substring match on the
# description) from all the given files, sorted chronologically.
def gather_event_instances(input_files, term):
    instances = []
    term_lower = term.lower()
    for path in input_files:
        with open(path, 'r') as csv_file:
            for row in csv.DictReader(csv_file):
                if term_lower in row['Description'].lower():
                    instances.append(entry_times(row))
    return sorted(instances)


# Week-by-week bar chart: how often the event occurred and for how long.
def print_weekly_chart(instances, term):
    weekly_count = defaultdict(int)
    weekly_hours = defaultdict(float)
    for start, end, duration in instances:
        monday = start.date() - timedelta(days=start.weekday())
        weekly_count[monday] += 1
        weekly_hours[monday] += duration.total_seconds() / 3600

    first_week = min(weekly_count)
    last_week = max(weekly_count)
    max_hours = max(weekly_hours.values())
    bar_width = 36

    print(f'\n{BLD}--- Weekly pattern for "{term}" ---{RST}')
    print(f'{DIM}{"Week of":<12}{"Count":>6}{"Hours":>8}  '
          f'(each full bar = {max_hours:.2f} h){RST}')

    # Walk every week in the range so gaps stay visible.
    week = first_week
    while week <= last_week:
        count = weekly_count.get(week, 0)
        hours = weekly_hours.get(week, 0.0)
        bar_len = round(hours / max_hours * bar_width) if max_hours else 0
        if count and bar_len == 0:
            bar_len = 1
        bar = GRN + '█' * bar_len + RST if bar_len else DIM + '·' + RST
        print(f'{week.strftime("%Y-%m-%d"):<12}{count:>6}{hours:>8.2f}  {bar}')
        week += timedelta(weeks=1)

    total_hours = sum(weekly_hours.values())
    n_weeks = ((last_week - first_week).days // 7) + 1
    print(f'\n{BLD}Total:{RST} {GRN}{len(instances)} instance(s), '
          f'{total_hours:.2f} hours across {n_weeks} week(s){RST} '
          f'{DIM}(avg {len(instances) / n_weeks:.1f}x/week, '
          f'{total_hours / n_weeks:.2f} h/week){RST}')


def report_event_instances(input_files, term):
    instances = gather_event_instances(input_files, term)

    if not instances:
        print(f'{RED}No instances of "{term}" found in the chosen file(s).{RST}')
        return

    span = f'{instances[0][0].strftime("%Y-%m-%d")} to {instances[-1][0].strftime("%Y-%m-%d")}'
    print(f'\nFound {GRN}{len(instances)}{RST} instance(s) of "{term}" '
          f'in {len(input_files)} file(s), spanning {span}.')

    if ask_yes_no('Print each individual instance to screen?', default=False):
        print(f'\n{BLD}--- "{term}" Instances ---{RST}')
        for start, end, _ in instances:
            print(f'Date: {start.strftime("%Y-%m-%d")}, '
                  f'Time window: {start.strftime("%H:%M")} - {end.strftime("%H:%M")}')

    if ask_yes_no('Show the weekly frequency chart?'):
        print_weekly_chart(instances, term)


MENU_ITEMS = [
    ('1', 'Merge a project\'s daily time ranges into a summary CSV'),
    ('2', 'Tally hours by project, task, and description'),
    ('3', 'Update tasks file with 15 most common descriptions'),
    ('4', 'Project hours by client and category'),
    ('5', 'Project hours by client/category/study over time'),
    ('6', 'Recurring event report (Metelao, Direitinha, ...)'),
    ('q', 'Quit'),
]


def print_menu():
    width = 56
    print()
    print(CYN + '╔' + '═' * width + '╗' + RST)
    print(CYN + '║' + RST + BLD + 'zToggl v1.2 — Toggl time-entry analyzer'.center(width) + RST + CYN + '║' + RST)
    print(CYN + '╠' + '═' * width + '╣' + RST)
    for key, label in MENU_ITEMS:
        line = f'  {YEL}{key}{RST}  {label}'
        # Pad to the box width, ignoring the ANSI escape codes.
        visible_len = 5 + len(label)
        print(CYN + '║' + RST + line + ' ' * (width - visible_len) + CYN + '║' + RST)
    print(CYN + '╚' + '═' * width + '╝' + RST)


def main():
    # Enable ANSI escape codes in the Windows console and make sure the
    # box-drawing characters survive consoles that default to cp1252.
    os.system('')
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    while True:
        print_menu()
        choice = input(f'{CYN}Your choice{RST}: ').strip().lower()

        if choice == 'q':
            print(f'{DIM}Goodbye.{RST}')
            break

        if choice not in ('1', '2', '3', '4', '5', '6'):
            print(f'{RED}Not a valid option.{RST}')
            continue

        # Option 6 can combine several files; the others work on one.
        selection = choose_input_csv(allow_all=(choice == '6'))
        if not selection:
            print(f'{RED}No input file chosen.{RST}')
            continue
        input_files = selection if isinstance(selection, list) else [selection]
        missing = [f for f in input_files if not os.path.isfile(f)]
        if missing:
            print(f'{RED}File not found: {missing[0]}{RST}')
            continue
        input_file = input_files[0]

        try:
            # Options 1, 4 and 5 analyze one project — let the user pick it.
            project = None
            if choice in ('1', '4', '5'):
                project = choose_project(input_file)
                if not project:
                    continue

            if choice == '1':
                parse_csv(input_file, choose_output_file('output_zT.csv'), project)
            elif choice == '2':
                tally_hours(input_file)
            elif choice == '3':
                common_tasks(input_file, choose_output_file('tasks_zT.csv'))
            elif choice == '4':
                report_hours_by_client_category(input_file, project)
            elif choice == '5':
                report_hours_by_client_over_time(input_file, choose_output_file('client_hours_report.csv'), project)
            elif choice == '6':
                term = choose_search_term(input_files)
                if term:
                    report_event_instances(input_files, term)
        except KeyError as e:
            print(f'{RED}The CSV is missing an expected column: {e}{RST}')

        input(f'\n{DIM}Press Enter to return to the menu...{RST}')


# This line ensures that main() gets called when this script is run directly.
if __name__ == '__main__':
    main()
