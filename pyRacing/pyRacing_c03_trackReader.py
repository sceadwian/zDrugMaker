"""
pyRacing_c03_trackReader.py

Part of a Formula 1 race simulation project. This script handles track analysis and preparation.

Key functions:
1. Reads and parses track layout from a CSV file
2. Analyzes track characteristics (length, sectors, turns, straights)
3. Generates a navigation path and segment sequence

Output:
- Displays ASCII track layout
- Prints navigation path and track analysis
- Saves track segment sequence (S: Start, I: Straight, U: Turn, X: Sector boundary) to CSV

Usage: Run script and enter track CSV filename when prompted.

This component prepares track data for the main race simulation, which will 
handle car movements, lap counting, and real-time race rendering.
"""

import os
import time
import csv

def load_track(file_path):
    with open(file_path, 'r') as file:
        return [line.strip().split(',') for line in file]

def find_start_position(track):
    for y, row in enumerate(track):
        for x, cell in enumerate(row):
            if cell.strip() == 'S':
                return x, y
    return None

def get_next_position(x, y, direction):
    if direction == 'N':
        return x, y - 1
    elif direction == 'E':
        return x + 1, y
    elif direction == 'S':
        return x, y + 1
    elif direction == 'W':
        return x - 1, y

def is_valid_position(track, x, y):
    return 0 <= y < len(track) and 0 <= x < len(track[y])

def is_track(cell):
    return cell.strip() in ['#', '$', 'S']

def determine_start_direction(track, start_x, start_y):
    directions = ['N', 'E', 'S', 'W']
    for direction in directions:
        next_x, next_y = get_next_position(start_x, start_y, direction)
        if is_valid_position(track, next_x, next_y) and is_track(track[next_y][next_x]):
            return direction
    return None

def analyze_track(track):
    start = find_start_position(track)
    if not start:
        return "Error: Start position 'S' not found."

    x, y = start
    direction = determine_start_direction(track, x, y)
    if not direction:
        return "Error: No valid starting direction found."

    path = []
    visited = set()
    segment_count = 0
    straight_count = 0
    turn_count = 0
    sector_borders = []
    sequence = ['S']  # Start with 'S' for the starting position

    while (x, y) not in visited:
        visited.add((x, y))
        segment_count += 1
        
        if track[y][x].strip() == '$':
            sector_borders.append(segment_count)
            sequence.append('X')  # Add 'X' for sector boundary
        
        # Check surrounding cells
        surroundings = {
            'N': is_track(track[y-1][x]) if is_valid_position(track, x, y-1) else False,
            'E': is_track(track[y][x+1]) if is_valid_position(track, x+1, y) else False,
            'S': is_track(track[y+1][x]) if is_valid_position(track, x, y+1) else False,
            'W': is_track(track[y][x-1]) if is_valid_position(track, x-1, y) else False
        }

        # Determine the next direction (always turn right first)
        right_direction = {'N': 'E', 'E': 'S', 'S': 'W', 'W': 'N'}[direction]
        if surroundings[right_direction]:  # Try turning right first
            path.append("Turn Right")
            direction = right_direction
            turn_count += 1
            sequence.append('U')  # Add 'U' for turn
        elif surroundings[direction]:  # Can continue straight
            path.append("Straight")
            straight_count += 1
            sequence.append('I')  # Add 'I' for straight
        else:
            # Try turning left last (clockwise)
            left_direction = {'N': 'W', 'W': 'S', 'S': 'E', 'E': 'N'}[direction]
            if surroundings[left_direction]:
                path.append("Turn Left")
                direction = left_direction
                turn_count += 1
                sequence.append('U')  # Add 'U' for turn
            else:
                return f"Error: Dead end at ({x}, {y})"

        # Update the position based on the new direction
        x, y = get_next_position(x, y, direction)
        if not is_valid_position(track, x, y) or not is_track(track[y][x]):
            return f"Error: Off track at ({x}, {y})"

    # Calculate track length and sector sizes
    track_length_km = segment_count * 20 / 1000
    sector_sizes = [
        sector_borders[0] * 20 / 1000,
        (sector_borders[1] - sector_borders[0]) * 20 / 1000,
        (segment_count - sector_borders[1]) * 20 / 1000
    ]

    return {
        'path': path,
        'track_length_km': track_length_km,
        'sector_sizes': sector_sizes,
        'straight_count': straight_count,
        'turn_count': turn_count,
        'sequence': sequence
    }

def save_sequence_to_csv(sequence, file_path):
    with open(file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(sequence)

def render_track(file_path):
    os.system('cls' if os.name == 'nt' else 'clear')
    track = load_track(file_path)
    for row in track:
        print(''.join(cell.strip() for cell in row))
    print("\nAnalyzing track...")
    time.sleep(2)
    
    result = analyze_track(track)
    if isinstance(result, str):  # Error message
        print(result)
    else:
        print("\nPath:")
        for i, move in enumerate(result['path'], 1):
            print(f"{i}. {move}")

        print("\nTrack analysis:")
        print(f"Track length: {result['track_length_km']:.2f} km")
        print(f"Sector 1 size: {result['sector_sizes'][0]:.2f} km")
        print(f"Sector 2 size: {result['sector_sizes'][1]:.2f} km")
        print(f"Sector 3 size: {result['sector_sizes'][2]:.2f} km")
        print(f"Number of straights: {result['straight_count']}")
        print(f"Number of turns: {result['turn_count']}")
        
        # Save sequence to CSV
        sequence_file_path = file_path.rsplit('.', 1)[0] + '_seq.csv'
        save_sequence_to_csv(result['sequence'], sequence_file_path)
        print(f"\nTrack sequence saved to: {sequence_file_path}")

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = input("Enter the track filename (press Enter for 'track.csv'): ").strip() or 'track.csv'
    file_path = os.path.join(current_dir, filename)

    if os.path.exists(file_path):
        render_track(file_path)
    else:
        print(f"Error: The file '{filename}' does not exist in the current directory.")

if __name__ == "__main__":
    main()
    time.sleep(30)