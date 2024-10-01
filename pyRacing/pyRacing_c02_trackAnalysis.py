import csv
import os
import time
from enum import Enum

class Direction(Enum):
    UP = 1
    DOWN = 2
    LEFT = 3
    RIGHT = 4

class TrackSegment:
    def __init__(self, is_turning, length, direction):
        self.is_turning = is_turning
        self.length = length
        self.direction = direction

class Track:
    def __init__(self):
        self.segments = []
        self.sector_boundaries = []
        self.total_length = 0

def analyze_track(file_path):
    with open(file_path, 'r') as file:
        reader = csv.reader(file)
        track_layout = [row for row in reader]

    # Find the starting position
    start_pos = None
    for y, row in enumerate(track_layout):
        for x, cell in enumerate(row):
            if cell.strip() == 'S':
                start_pos = (x, y)
                break
        if start_pos:
            break

    if not start_pos:
        raise ValueError("Starting position 'S' not found in the track layout.")

    track = Track()
    current_pos = start_pos
    current_direction = Direction.LEFT  # Start by going left
    segment_length = 0
    is_turning = False

    directions = [
        Direction.LEFT, Direction.LEFT, Direction.LEFT, Direction.LEFT, Direction.LEFT, Direction.LEFT, Direction.LEFT,
        Direction.UP, Direction.UP,
        Direction.RIGHT, Direction.RIGHT, Direction.RIGHT, Direction.RIGHT, Direction.RIGHT, Direction.RIGHT,
        Direction.RIGHT, Direction.RIGHT, Direction.RIGHT, Direction.RIGHT, Direction.RIGHT, Direction.RIGHT,
        Direction.RIGHT, Direction.DOWN, Direction.DOWN,
        Direction.LEFT, Direction.LEFT, Direction.LEFT, Direction.LEFT, Direction.LEFT, Direction.LEFT, Direction.LEFT
    ]

    for i, direction in enumerate(directions):
        if direction != current_direction:
            if segment_length > 0:
                track.segments.append(TrackSegment(is_turning, segment_length * 20, current_direction))
                track.total_length += segment_length * 20
            segment_length = 0
            is_turning = True
            current_direction = direction
        
        segment_length += 1

        # Check for sector boundaries
        x, y = current_pos
        if track_layout[y][x].strip() == '$':
            track.sector_boundaries.append(track.total_length + segment_length * 20)

        # Move to next position
        if direction == Direction.UP:
            current_pos = (x, y - 1)
        elif direction == Direction.DOWN:
            current_pos = (x, y + 1)
        elif direction == Direction.LEFT:
            current_pos = (x - 1, y)
        elif direction == Direction.RIGHT:
            current_pos = (x + 1, y)

    # Add the final segment
    if segment_length > 0:
        track.segments.append(TrackSegment(is_turning, segment_length * 20, current_direction))
        track.total_length += segment_length * 20

    return track

def render_track(file_path):
    with open(file_path, 'r') as file:
        track_lines = [line.rstrip().replace(',', '') for line in file.readlines()]
    for line in track_lines:
        print(line)

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = input("Enter the track filename (press Enter for 'track_sample.csv'): ").strip()
    if not filename:
        filename = 'track_sample.csv'
    file_path = os.path.join(current_dir, filename)

    if os.path.exists(file_path):
        print("Track Layout:")
        render_track(file_path)
        print("\nAnalyzing track...\n")
        track = analyze_track(file_path)
        print(f"Total track length: {track.total_length} meters")
        print(f"Number of segments: {len(track.segments)}")
        print(f"Sector boundaries: {track.sector_boundaries}")
        for i, segment in enumerate(track.segments):
            print(f"Segment {i + 1}: {'Turn' if segment.is_turning else 'Straight'}, "
                  f"Length: {segment.length}m, Direction: {segment.direction.name}")
    else:
        print(f"Error: The file '{filename}' does not exist in the current directory.")
        time.sleep(10)

if __name__ == "__main__":
    main()