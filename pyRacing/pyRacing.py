import os
import time

# Get the directory where the Python script is running
current_dir = os.path.dirname(os.path.abspath(__file__))
# Define the path to the CSV file in the same directory
file_path = os.path.join(current_dir, 'track.csv')

# Function to load and display the track from the CSV file
def load_track(file_path):
    with open(file_path, 'r') as file:
        # Read all lines from the file
        track_lines = [line.rstrip() for line in file.readlines()]  # rstrip to remove trailing newline
    return track_lines

# Function to render the track
def render_track(file_path):
    os.system('cls' if os.name == 'nt' else 'clear')
    track_lines = load_track(file_path)
    for line in track_lines:
        print(line)
    time.sleep(11)  # Pause to simulate real-time rendering

# Call the render function to show the track
render_track(file_path)
