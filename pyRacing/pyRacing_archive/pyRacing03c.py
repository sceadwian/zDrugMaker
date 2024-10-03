#version 3b fixed the simulation a bit. some minor tweaks to prevent cars from halting.
#version 3c added more to the reporting of the race.

import os
import time
import random
import csv
from datetime import datetime

class Car:
    def __init__(self, symbol, cc_maxSpd, cc_accel, cc_dragC, cc_downC, cc_cornr):
        self.symbol = symbol
        self.cc_maxSpd = cc_maxSpd
        self.cc_accel = cc_accel
        self.cc_dragC = cc_dragC
        self.cc_downC = cc_downC
        self.cc_cornr = cc_cornr
        self.distance = 0  # Distance traveled in meters
        self.speed = 0  # Current speed in km/h
        self.laps_completed = 0
        self.lap_times = []
        self.best_lap_time = float('inf')
        self.current_lap_start_time = 0
        self.finished = False  # New attribute to track if a car has finished the race
        self.total_race_time = 0  # New attribute to track total race time

    def update_speed_turn(self):
        # Adjust speed based on cornering and downforce
        self.speed = self.speed * (0.4 + (self.cc_cornr / 200) + (self.cc_downC / 2000))
        # Ensure that the speed does not fall below 50 km/h
        if self.speed < 50:
            self.speed = 50

    def update_speed_straight(self, random_factor):
        new_speed = (self.speed + 
                     0.2 * random_factor * (self.cc_downC + self.cc_dragC - self.cc_accel) + 
                     (self.cc_accel / 2) - 
                     self.speed * (1 - (self.cc_dragC / 500)) * (0.10 + 0.31 * ((self.speed**0.5 - 100) / 1500)) - 
                     self.speed * (self.cc_downC / 5000))
        self.speed = min(new_speed, self.cc_maxSpd)

    def move(self, track_sequence, track_length, time_step, current_time, num_laps):
        if not self.finished:
            current_tile_index = int(self.distance / 20) % len(track_sequence)
            current_tile = track_sequence[current_tile_index]
            is_turning = current_tile == 'U'
        
            if is_turning:
                self.update_speed_turn()
            else:
                self.update_speed_straight(random.uniform(0.8, 1.2))
        
            # Calculate distance moved in this time step
            distance_moved = (self.speed * 1000 / 3600) * time_step  # Convert km/h to m/s and multiply by time
            self.distance += distance_moved
        
            # Check if a lap is completed
            if self.distance >= track_length:
                self.laps_completed += 1
                self.distance %= track_length
        
                # Correctly calculate the lap time
                lap_time = current_time - self.current_lap_start_time
                if lap_time > 0:  # Ensure the time is positive
                    self.lap_times.append(lap_time)
                    if lap_time < self.best_lap_time:
                        self.best_lap_time = lap_time
        
                # Reset the lap start time to the current time
                self.current_lap_start_time = current_time
            
            # Check if the car has completed all laps
            if self.laps_completed >= num_laps:
                self.finished = True
                self.distance = self.laps_completed * track_length  # Ensure finished cars are ranked correctly
                self.total_race_time = current_time  # Record total race time

def load_track_visual(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file.readlines()]

def load_track_sequence(file_path):
    with open(file_path, 'r') as file:
        return file.read().strip().split(',')

def render_race_progress(cars, track_length, display_width=80):
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # Sort cars by whether they have finished and their total distance covered
    sorted_cars = sorted(cars, key=lambda car: (car.finished, car.laps_completed * track_length + car.distance), reverse=True)
    
    for i, car in enumerate(sorted_cars, 1):
        progress = int((car.distance / track_length) * display_width)
        best_lap = f"{car.best_lap_time:.2f} s" if car.best_lap_time != float('inf') else "N/A"
        line = f"{i:2d}. {car.symbol} |" + "=" * progress + " " * (display_width - progress) + f"| Lap {car.laps_completed + 1} - Best Lap: {best_lap}"
        print(line)
    
    print("\nCar Details:")
    for i, car in enumerate(sorted_cars, 1):
        print(f"{i:2d}. {car.symbol}: Distance: {car.distance:.2f} m, Speed: {car.speed:.2f} km/h")
    
    time.sleep(0.1)

def simulate_race(track_sequence, cars, num_laps, time_step=0.1):
    track_length = len(track_sequence) * 20  # Each segment is 20m
    start_time = time.time()
    
    for car in cars:
        car.current_lap_start_time = start_time
    
    while any(car.laps_completed < num_laps for car in cars):
        current_time = time.time() - start_time
        for car in cars:
            if not car.finished:
                car.move(track_sequence, track_length, time_step, current_time, num_laps)
        
        render_race_progress(cars, track_length)

def write_race_results(cars, filename):
    # Sort cars by their finishing order
    sorted_cars = sorted(cars, key=lambda car: (car.finished, car.laps_completed * len(track_sequence) * 20 + car.distance), reverse=True)
    
    with open(filename, 'w') as f:
        f.write("Race Results\n")
        f.write("============\n\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("Pos | Car | Best Lap   | Total Time\n")
        f.write("----+-----+------------+------------\n")
        
        for i, car in enumerate(sorted_cars, 1):
            best_lap = f"{car.best_lap_time:.2f} s" if car.best_lap_time != float('inf') else "N/A"
            total_time = f"{car.total_race_time:.2f} s" if car.finished else "DNF"
            f.write(f"{i:3d} | {car.symbol:3s} | {best_lap:10s} | {total_time:10s}\n")

def write_race_results(cars, filename, track_length):
    # Sort cars by their finishing order
    sorted_cars = sorted(cars, key=lambda car: (car.finished, car.laps_completed * track_length + car.distance), reverse=True)
    
    with open(filename, 'w') as f:
        f.write("Race Results\n")
        f.write("============\n\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("Pos | Car | Best Lap   | Total Time\n")
        f.write("----+-----+------------+------------\n")
        
        for i, car in enumerate(sorted_cars, 1):
            best_lap = f"{car.best_lap_time:.2f} s" if car.best_lap_time != float('inf') else "N/A"
            total_time = f"{car.total_race_time:.2f} s" if car.finished else "DNF"
            f.write(f"{i:3d} | {car.symbol:3s} | {best_lap:10s} | {total_time:10s}\n")


def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Load visual track and display it
    track_filename = input("Enter the visual track filename (e.g. 'track_1.csv'): ").strip()
    track_visual = load_track_visual(os.path.join(current_dir, track_filename))
    
    print("Track Layout:")
    for row in track_visual:
        print(row)
    print("\nPress Enter to start the race...")
    input()

    # Load track sequence
    seq_filename = track_filename.replace('.csv', '_seq.csv')
    track_sequence = load_track_sequence(os.path.join(current_dir, seq_filename))

    # Calculate track length
    track_length = len(track_sequence) * 20  # Each segment is 20m

    # Initialize cars
    cars = [Car(symbol=chr(65 + i), cc_maxSpd=random.randint(300, 350),
                cc_accel=random.randint(50, 70), cc_dragC=random.randint(50, 70),
                cc_downC=random.randint(50, 70), cc_cornr=random.randint(50, 70))
            for i in range(20)]

    # Start the race simulation
    simulate_race(track_sequence, cars, num_laps=5)

    # Write race results to a log file
    log_filename = f"race_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    write_race_results(cars, os.path.join(current_dir, log_filename), track_length)
    print(f"\nRace results have been written to {log_filename}")

if __name__ == "__main__":
    main()