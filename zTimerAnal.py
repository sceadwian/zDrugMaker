import os
from datetime import datetime

def parse_event_log(file_path):
    """
    Parse the behavior log file and extract the event log section.
    Returns a list of dictionaries containing event data.
    """
    events = []
    reading_events = False
    header = None
    
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            
            # Find the start of the event log section
            if line == "Detailed Event Log:":
                reading_events = True
                continue
            
            if reading_events:
                if not header:
                    # Parse header line
                    header = [col.strip() for col in line.split('\t')]
                    continue
                
                if line:  # Skip empty lines
                    values = line.split('\t')
                    if len(values) == len(header):
                        event = {}
                        for i, col in enumerate(header):
                            event[col] = values[i]
                        # Convert numeric values
                        event['Start(s)'] = float(event['Start(s)'])
                        event['End(s)'] = float(event['End(s)'])
                        event['Duration(s)'] = float(event['Duration(s)'])
                        events.append(event)
    
    return events

def analyze_time_blocks(events, block_size_minutes):
    """
    Analyze events in time blocks of specified size.
    Returns a list of dictionaries containing analysis for each time block.
    """
    block_size_seconds = block_size_minutes * 60
    
    # Find total duration
    total_duration = max(event['End(s)'] for event in events)
    num_blocks = int((total_duration + block_size_seconds - 1) // block_size_seconds)
    
    # Get unique keys
    keys = sorted(set(event['Key'] for event in events))
    
    analysis_results = []
    
    for block in range(num_blocks):
        start_time = block * block_size_seconds
        end_time = (block + 1) * block_size_seconds
        
        block_summary = {
            'block_number': block + 1,
            'time_range': f"{start_time/60:.1f}-{min(end_time, total_duration)/60:.1f} min"
        }
        
        # Analyze each key type
        for key in keys:
            # Filter events for this key and block
            key_events = [
                event for event in events 
                if event['Key'] == key and 
                (
                    (event['Start(s)'] >= start_time and event['Start(s)'] < end_time) or
                    (event['End(s)'] > start_time and event['End(s)'] <= end_time) or
                    (event['Start(s)'] <= start_time and event['End(s)'] >= end_time)
                )
            ]
            
            # Calculate total duration within this block
            total_duration_in_block = 0
            for event in key_events:
                event_start = max(event['Start(s)'], start_time)
                event_end = min(event['End(s)'], end_time)
                total_duration_in_block += max(0, event_end - event_start)
            
            block_summary[f"{key}_count"] = len(key_events)
            block_summary[f"{key}_duration"] = total_duration_in_block
            block_summary[f"{key}_percentage"] = (total_duration_in_block / block_size_seconds) * 100
        
        analysis_results.append(block_summary)
    
    return analysis_results

def display_results(analysis_results, keys):
    """
    Display the analysis results in a formatted table.
    """
    # Print header
    print("\nAnalysis Results:")
    print("=" * 120)
    
    # Create header row
    header = ["Block", "Time Range"]
    for key in keys:
        header.extend([f"{key} Count", f"{key} Duration (s)", f"{key} %"])
    
    # Print header
    header_format = "{:<6} {:<15}" + " {:<10} {:<14} {:<8}" * len(keys)
    print(header_format.format(*header))
    print("-" * 120)
    
    # Print data rows
    row_format = "{:<6} {:<15}" + " {:<10} {:<14.2f} {:<8.2f}" * len(keys)
    for result in analysis_results:
        row_data = [
            f"#{result['block_number']}", 
            result['time_range']
        ]
        for key in keys:
            row_data.extend([
                result[f"{key}_count"],
                result[f"{key}_duration"],
                result[f"{key}_percentage"]
            ])
        print(row_format.format(*row_data))
    
    print("=" * 120)

def save_results(analysis_results, keys, output_file):
    """
    Save the analysis results to a CSV file.
    """
    with open(output_file, 'w') as f:
        # Write header
        header = ["Block", "Time Range"]
        for key in keys:
            header.extend([f"{key}_Count", f"{key}_Duration", f"{key}_Percentage"])
        f.write(','.join(header) + '\n')
        
        # Write data rows
        for result in analysis_results:
            row = [
                str(result['block_number']),
                result['time_range']
            ]
            for key in keys:
                row.extend([
                    str(result[f"{key}_count"]),
                    f"{result[f'{key}_duration']:.2f}",
                    f"{result[f'{key}_percentage']:.2f}"
                ])
            f.write(','.join(row) + '\n')

def main():
    print("Behavior Log Analysis Tool")
    print("-" * 50)
    
    # List available log files in current directory
    log_files = [f for f in os.listdir() if f.startswith("behavior_log_") and f.endswith(".txt")]
    
    if not log_files:
        print("No behavior log files found in current directory.")
        return
    
    print("\nAvailable log files:")
    for i, file in enumerate(log_files, 1):
        print(f"{i}. {file}")
    
    # Get file selection from user
    while True:
        try:
            selection = int(input("\nEnter the number of the file to analyze: "))
            if 1 <= selection <= len(log_files):
                file_path = log_files[selection - 1]
                break
            print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a valid number.")
    
    # Get block size from user
    while True:
        try:
            block_size = float(input("\nEnter the size of time blocks (in minutes): "))
            if block_size <= 0:
                raise ValueError
            break
        except ValueError:
            print("Please enter a valid positive number")
    
    try:
        # Parse and analyze the data
        print("\nAnalyzing data...")
        events = parse_event_log(file_path)
        keys = sorted(set(event['Key'] for event in events))
        analysis_results = analyze_time_blocks(events, block_size)
        
        # Display results
        display_results(analysis_results, keys)
        
        # Save results to CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"behavior_analysis_{timestamp}.csv"
        save_results(analysis_results, keys, output_file)
        print(f"\nResults saved to: {output_file}")
        
    except Exception as e:
        print(f"Error analyzing file: {e}")

if __name__ == "__main__":
    main()