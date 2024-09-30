import os
import time
import csv
from typing import List, Tuple

class Car:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.position = (0, 0)  # (x, y) coordinates
        self.lap = 0

    def move(self, new_position: Tuple[int, int]):
        self.position = new_position

class Track:
    def __init__(self, layout: List[str]):
        self.layout = layout
        self.start_position = self.find_start_position()
        self.cars = [
            Car('A'), Car('B'), Car('C'), Car('D'), Car('E'),
            Car('F'), Car('G'), Car('H'), Car('I'), Car('J'),
            Car('K'), Car('L'), Car('M'), Car('N')
        ]
        self.place_cars_at_start()

    def find_start_position(self) -> Tuple[int, int]:
        for y, row in enumerate(self.layout):
            if 'S' in row:
                return (row.index('S'), y)
        # If 'S' is not found, use the first '#' character as the start position
        for y, row in enumerate(self.layout):
            if '#' in row:
                return (row.index('#'), y)
        raise ValueError("No valid start position found in track layout")

    def place_cars_at_start(self):
        for car in self.cars:
            car.position = self.start_position

    def render(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        rendered_layout = self.layout.copy()
        
        # Place cars on the track
        for car in self.cars:
            x, y = car.position
            row = list(rendered_layout[y])
            row[x] = car.symbol
            rendered_layout[y] = ''.join(row)
        
        # Print the rendered track
        for line in rendered_layout:
            print(line)
        
        # Print car information
        print("\nCar Positions:")
        for car in self.cars:
            print(f"{car.symbol}: Lap {car.lap}, Position {car.position}")

def load_track(file_path: str) -> List[str]:
    with open(file_path, 'r', newline='') as file:
        reader = csv.reader(file)
        track_lines = [','.join(row).replace(',', '') for row in reader if row]
    
    # Debugging: Print the loaded track
    print(f"Loaded track layout ({len(track_lines)} lines):")
    for i, line in enumerate(track_lines):
        print(f"{i:2d}: {line}")
    print("End of track layout")
    
    return track_lines

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = input("Enter the track filename (press Enter for 'track.csv'): ").strip() or 'track.csv'
    file_path = os.path.join(current_dir, filename)

    if os.path.exists(file_path):
        try:
            track_layout = load_track(file_path)
            if not track_layout:
                raise ValueError("The track file is empty or contains no valid data.")
            track = Track(track_layout)
            
            # Simulate a few rendering cycles
            for _ in range(5):
                track.render()
                time.sleep(1)
        except Exception as e:
            print(f"An error occurred: {e}")
            print("Please check the contents of your track file and ensure it's formatted correctly.")
    else:
        print(f"Error: The file '{filename}' does not exist in the current directory.")

if __name__ == "__main__":
    main()
    