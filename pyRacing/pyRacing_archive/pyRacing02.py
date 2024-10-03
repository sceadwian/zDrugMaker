import os
import time

import random

class Car:
    def __init__(self, symbol, cc_maxSpd, cc_accel, cc_dragC, cc_downC, cc_cornr):
        self.symbol = symbol
        self.cc_maxSpd = cc_maxSpd
        self.cc_accel = cc_accel
        self.cc_dragC = cc_dragC
        self.cc_downC = cc_downC
        self.cc_cornr = cc_cornr
        self.position = 21  # Default position
        self.speed = 0  # Current speed in km/h
        self.lap = 0

    def __str__(self):
        return (f"Car {self.symbol}: "
                f"Max Speed: {self.cc_maxSpd}, "
                f"Acceleration: {self.cc_accel}, "
                f"Drag Coefficient: {self.cc_dragC}, "
                f"Downforce Coefficient: {self.cc_downC}, "
                f"Cornering Coefficient: {self.cc_cornr}, "
                f"Position: {self.position}, "
                f"Current Speed: {self.speed:.2f} km/h")

    def update_speed_turn(self):
        self.speed = self.speed * (0.4 + (self.cc_cornr / 200) + (self.cc_downC / 2000))

    def update_speed_straight(self, random_factor):
        new_speed = (self.speed + 
                     0.2 * random_factor * (self.cc_downC + self.cc_dragC - self.cc_accel) + 
                     (self.cc_accel / 2.5) - 
                     self.speed * (1 - (self.cc_dragC / 500)) * (0.10 + 0.31 * ((self.speed**0.5 - 100) / 1500)) - 
                     self.speed * (self.cc_downC / 5000))
        self.speed = min(new_speed, self.cc_maxSpd)  # Ensure speed doesn't exceed max speed

    def move(self, is_turning, random_factor):
        if is_turning:
            self.update_speed_turn()
        else:
            self.update_speed_straight(random_factor)
        # Update position logic would go here

# Create 20 cars with random attributes
cars = []
for i in range(20):
    car = Car(
        symbol=chr(65 + i),  # A, B, C, ...
        cc_maxSpd=random.randint(300, 350),
        cc_accel=random.randint(1, 100),
        cc_dragC=random.randint(1, 100),
        cc_downC=random.randint(1, 100),
        cc_cornr=random.randint(1, 100)
    )
    cars.append(car)

# Example of moving a car
for car in cars:
    is_turning = random.choice([True, False])  # This would be determined by your track logic
    random_factor = random.uniform(0, 0.5)
    car.move(is_turning, random_factor)
    print(car)

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
