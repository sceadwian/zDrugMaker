"""
pyRacing_b01_showsTrack.py

Part of a Formula 1 race simulation project. This script visualizes track layouts with color-coded elements.

Key functions:
1. Loads track layout from a CSV file
2. Renders the track with colored elements (Start, Sector boundaries)
3. Provides a simple user interface for file selection

Output:
- Displays color-coded ASCII track layout in the terminal
  - Green: Start line
  - Yellow: First sector boundary
  - Red: Second sector boundary

Usage: Run script and enter track CSV filename when prompted, or press Enter for default 'track.csv'.

This component serves as a visual aid for track layout verification and can be integrated
into a larger race simulation system for pre-race track analysis and setup.
"""

import os
import time

# ANSI escape codes for colors
RESET = '\033[0m'
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'

# Function to load and display the track from the CSV file
def load_track(file_path):
    with open(file_path, 'r') as file:
        # Read all lines from the file
        track_lines = [line.rstrip() for line in file.readlines()]  # rstrip to remove trailing newline
    return track_lines

# Function to render the track with colored elements
def render_track(file_path):
    os.system('cls' if os.name == 'nt' else 'clear')
    track_lines = load_track(file_path)
    
    for i, line in enumerate(track_lines):
        colored_line = ''
        for j, char in enumerate(line):
            if char == 'S':
                colored_line += GREEN + char + RESET
            elif char == '$':
                colored_line += YELLOW + char + RESET
            elif char == '2':
                colored_line += RED + char + RESET
            else:
                colored_line += char
        print(colored_line)
    
    time.sleep(12)  # Pause to simulate real-time rendering

# Main function to handle user input and loading the correct track file
def main():
    # Get the directory where the Python script is running
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Prompt the user for a filename
    filename = input("Enter the track filename (press Enter for 'track.csv'): ").strip()

    # Default to 'track.csv' if the user presses Enter without input
    if not filename:
        filename = 'track.csv'
    
    # Construct the file path
    file_path = os.path.join(current_dir, filename)

    # Check if the file exists before attempting to load it
    if os.path.exists(file_path):
        render_track(file_path)
    else:
        print(f"Error: The file '{filename}' does not exist in the current directory.")

# Call the main function to start the program
if __name__ == "__main__":
    main()