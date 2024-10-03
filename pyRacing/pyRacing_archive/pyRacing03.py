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
        self.position = 0  # Position in the sequence
        self.speed = 0  # Current speed in km/h
        self.laps_completed = 0

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
        self.speed = min(new_speed, self.cc_maxSpd)

    def move(self, track_sequence, random_factor):
        current_tile = track_sequence[self.position]
        is_turning = current_tile == 'U'

        if is_turning:
            self.update_speed_turn()
        else:
            self.update_speed_straight(random_factor)

        # Move forward based on speed
        self.position = (self.position + int(self.speed // 20)) % len(track_sequence)
        
        # Check if a lap is completed
        if self.position < int(self.speed // 20):
            self.laps_completed += 1

def load_track_visual(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file.readlines()]

def load_track_sequence(file_path):
    with open(file_path, 'r') as file:
        return file.read().strip().split(',')

def render_track(track_visual, cars, track_sequence):
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # Create a copy of the visual track
    track_copy = [list(row) for row in track_visual]
    
    # Find the positions to place cars
    track_positions = [(i, j) for i, row in enumerate(track_visual) for j, char in enumerate(row) if char in '#S$']
    
    for car in cars:
        if car.position < len(track_positions):
            y, x = track_positions[car.position]
            track_copy[y][x] = car.symbol
    
    for row in track_copy:
        print("".join(row))
    
    print("\nCar Positions:")
    for car in cars:
        print(f"{car.symbol}: Lap {car.laps_completed + 1}, Position: {car.position}, Speed: {car.speed:.2f} km/h")
    
    time.sleep(0.5)

def simulate_race(track_visual, track_sequence, cars, num_laps):
    while any(car.laps_completed < num_laps for car in cars):
        for car in cars:
            if car.laps_completed < num_laps:
                random_factor = random.uniform(0, 0.5)
                car.move(track_sequence, random_factor)
        
        render_track(track_visual, cars, track_sequence)

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Load visual track
    track_filename = input("Enter the visual track filename (e.g. 'track_1.csv'): ").strip()
    track_visual = load_track_visual(os.path.join(current_dir, track_filename))

    # Load track sequence
    seq_filename = track_filename.replace('.csv', '_seq.csv')
    track_sequence = load_track_sequence(os.path.join(current_dir, seq_filename))

    # Initialize cars
    cars = [Car(symbol=chr(65 + i), cc_maxSpd=random.randint(300, 350),
                cc_accel=random.randint(50, 70), cc_dragC=random.randint(50, 70),
                cc_downC=random.randint(50, 70), cc_cornr=random.randint(50, 70))
            for i in range(20)]

    # Start the race simulation
    simulate_race(track_visual, track_sequence, cars, num_laps=3)

if __name__ == "__main__":
    main()