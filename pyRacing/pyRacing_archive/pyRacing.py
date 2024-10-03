import os
import time

# Function to load and display the track from the CSV file
def load_track(file_path):
    with open(file_path, 'r') as file:
        # Read all lines from the file and remove commas from each line
        track_lines = [line.rstrip().replace(',', '') for line in file.readlines()]  # Remove trailing newlines and commas
    return track_lines

# Function to render the track
def render_track(file_path):
    os.system('cls' if os.name == 'nt' else 'clear')
    track_lines = load_track(file_path)
    for line in track_lines:
        print(line)
    time.sleep(1)  # Pause to simulate real-time rendering

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
        time.sleep(10)

# Call the main function to start the program
if __name__ == "__main__":
    main()
